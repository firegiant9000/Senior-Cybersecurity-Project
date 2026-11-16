"""Activation analytics — onboarding funnel events (Month 2 Phase F4).

Lightweight client-side event log. Goal is to measure whether the
onboarding collapse (Phase B) actually improves time-to-value. All
event payloads pass through the observability scrubber on the way
in so we never persist PII even if a caller sends a hostname or
email by mistake (R10).

Events are always stored under the caller's own organization; a body org_id
that differs from it is refused (T-TEN-10).

Allowed event types are pinned — unknown types are rejected so clients
can't grow the schema implicitly.

Admins can also read the anonymous public-readiness funnel counters (#296).
"""

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import require_role
from app.core.limiter import limiter
from app.core.observability import _scrub
from app.db.activation_event import ActivationEvent
from app.db.engine import get_session
from app.db.user import User
from app.repositories.readiness_funnel import (
    SqlReadinessFunnelRepository,
    get_readiness_funnel_repo,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Closed set — see month_2_execution_plan.md Phase F4 for the canonical list.
ALLOWED_EVENT_TYPES = frozenset(
    {
        "intake_step_skipped",
        "csv_upload_started",
        "csv_upload_completed",
        "m365_connect_started",
        "m365_connect_completed",
        "dashboard_first_view",
    }
)

# Hard cap so a misbehaving client can't push large payloads. Anything
# bigger than this is almost certainly the wrong shape.
_MAX_PAYLOAD_KEYS = 20


class ActivationEventCreate(BaseModel):
    event_type: str = Field(..., max_length=64)
    org_id: int | None = None
    payload: dict[str, Any] | None = None


class ActivationEventAck(BaseModel):
    id: int  # noqa: A003
    event_type: str


@router.post("/analytics/events", response_model=ActivationEventAck)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def record_event(
    request: Request,  # noqa: ARG001 — required by limiter
    body: ActivationEventCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ActivationEventAck:
    """Record one activation event. Best-effort; failures are non-fatal to the UI."""
    if body.org_id is not None and body.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if body.event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown event_type")

    payload = body.payload or {}
    if len(payload) > _MAX_PAYLOAD_KEYS:
        raise HTTPException(status_code=400, detail="payload has too many keys")
    scrubbed = _scrub(payload) if payload else None

    event = ActivationEvent(
        event_type=body.event_type,
        org_id=current_user.org_id,
        user_id=current_user.id,
        payload=scrubbed,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return ActivationEventAck(id=event.id, event_type=event.event_type)


_FUNNEL_NOTE = (
    "Directional only: anyone can call the counting route, so these numbers can be inflated."
)
_FUNNEL_MAX_SPAN_DAYS = 365


class ReadinessFunnelCountOut(BaseModel):
    day: date
    version: str
    step: str
    count: int


class ReadinessFunnelResponse(BaseModel):
    start: date
    end: date
    counts: list[ReadinessFunnelCountOut]
    note: str


@router.get("/analytics/readiness-funnel", response_model=ReadinessFunnelResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_readiness_funnel(
    request: Request,  # noqa: ARG001 — required by limiter
    start: date,
    end: date,
    repo: SqlReadinessFunnelRepository = Depends(get_readiness_funnel_repo),
    _: User = Depends(require_role("admin")),
) -> ReadinessFunnelResponse:
    """Anonymous public-readiness funnel counts per day/version/step (admin only)."""
    if end < start:
        raise HTTPException(status_code=422, detail="end must not be before start")
    if (end - start).days > _FUNNEL_MAX_SPAN_DAYS:
        raise HTTPException(status_code=422, detail="range is limited to 366 days")
    rows = await repo.counts_between(start, end)
    return ReadinessFunnelResponse(
        start=start,
        end=end,
        counts=[
            ReadinessFunnelCountOut(day=r.day, version=r.version, step=r.step, count=r.count)
            for r in rows
        ],
        note=_FUNNEL_NOTE,
    )
