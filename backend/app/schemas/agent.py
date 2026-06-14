"""Pydantic schemas for agent enrollment endpoints (Month 4 Phase 1).

The raw token never appears in ``AgentRead`` — only in ``AgentTokenIssued``,
which is returned exactly once at issue/rotate time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.config import settings

AgentStatus = Literal["active", "grace", "stale", "revoked", "expired"]


class AgentCreate(BaseModel):
    """Admin-supplied fields when enrolling a new agent."""

    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] | None = Field(default=None)


class AgentRead(BaseModel):
    """Safe representation of an enrollment — never exposes the secret."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int  # noqa: A003
    org_id: int
    name: str
    token_prefix: str
    scopes: list[str] | None
    created_by_user_id: int | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    expires_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> AgentStatus:
        """Derive a display status from the lifecycle timestamps.

        Order matters: a revoked/expired token is never "stale". ``revoked_at``
        in the future means a rotation grace window is still open.
        """
        now = datetime.now(UTC)
        revoked = _as_aware(self.revoked_at)
        expires = _as_aware(self.expires_at)
        last_used = _as_aware(self.last_used_at)

        if revoked is not None and revoked <= now:
            return "revoked"
        if expires is not None and expires <= now:
            return "expired"
        if revoked is not None and revoked > now:
            return "grace"
        stale_after = timedelta(days=settings.AGENT_INACTIVE_AFTER_DAYS)
        reference = last_used or _as_aware(self.created_at)
        if reference is not None and now - reference > stale_after:
            return "stale"
        return "active"


class AgentListResponse(BaseModel):
    total: int
    items: list[AgentRead]


class AgentTokenIssued(BaseModel):
    """One-time response carrying the raw token. Never persisted, never re-shown."""

    model_config = ConfigDict(from_attributes=True)

    agent: AgentRead
    raw_token: str = Field(description="Full bearer token; shown once and unrecoverable.")


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
