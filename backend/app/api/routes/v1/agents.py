"""Agent enrollment management routes (Month 4 Phase 2).

Admin-only, Firebase-authed human endpoints to enroll / list / rotate / revoke
the per-host scanner credentials minted by ``services/agent_token.py`` (Phase 1).
These are the *management* surface; the scanner itself authenticates with the
issued bearer token against the Phase 3 upload endpoint, never here.

Org is derived from the caller's session (``get_current_org``) — an admin can
only manage their own org's agents, mirroring the (org_id, agent_id) identity
frozen in ``docs/month_4_phase0_closeout.md`` Step 2.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.inventory import _audit
from app.core.config import settings
from app.core.dependencies import get_current_org, require_org_role
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.organization import Organization
from app.db.user import User
from app.repositories.agent_enrollments import (
    SqlAgentEnrollmentRepository,
    get_agent_enrollment_repo,
)
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentRead,
    AgentTokenIssued,
)
from app.services import agent_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/enroll", response_model=AgentTokenIssued, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def enroll_agent(
    request: Request,  # noqa: ARG001 — required by limiter
    body: AgentCreate,
    current_user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    repo: SqlAgentEnrollmentRepository = Depends(get_agent_enrollment_repo),
    session: AsyncSession = Depends(get_session),
):
    """Mint a new per-agent bearer token for the caller's org.

    The raw token is returned **once** in ``AgentTokenIssued.raw_token`` and is
    never retrievable again — losing it means re-enrolling. Only the hash and
    prefix are persisted.
    """
    issued = await agent_token.issue(
        repo,
        org_id=org.id,
        name=body.name,
        scopes=body.scopes,
        created_by_user_id=current_user.id,
    )
    await _audit_safe(
        session,
        actor=current_user,
        org_id=org.id,
        action="agent.enroll",
        payload={"agent_id": issued.enrollment.id, "name": body.name},
    )
    return AgentTokenIssued(
        agent=AgentRead.model_validate(issued.enrollment),
        raw_token=issued.raw_token,
    )


@router.get("", response_model=AgentListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_agents(
    request: Request,  # noqa: ARG001
    _user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    repo: SqlAgentEnrollmentRepository = Depends(get_agent_enrollment_repo),
):
    """List the org's agents, newest first, with derived status and last_used_at."""
    rows = await repo.list_for_org(org.id)
    return AgentListResponse(
        total=len(rows),
        items=[AgentRead.model_validate(r) for r in rows],
    )


@router.post("/{agent_id}/rotate", response_model=AgentTokenIssued)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def rotate_agent(
    request: Request,  # noqa: ARG001
    agent_id: int,
    current_user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    repo: SqlAgentEnrollmentRepository = Depends(get_agent_enrollment_repo),
    session: AsyncSession = Depends(get_session),
):
    """Issue a replacement token; the old one stays valid for the 24h grace window."""
    enrollment = await repo.get_by_id(agent_id, org.id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    issued = await agent_token.rotate(repo, enrollment, created_by_user_id=current_user.id)
    await _audit_safe(
        session,
        actor=current_user,
        org_id=org.id,
        action="agent.rotate",
        payload={"old_agent_id": agent_id, "new_agent_id": issued.enrollment.id},
    )
    return AgentTokenIssued(
        agent=AgentRead.model_validate(issued.enrollment),
        raw_token=issued.raw_token,
    )


@router.delete("/{agent_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def revoke_agent(
    request: Request,  # noqa: ARG001
    agent_id: int,
    current_user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    repo: SqlAgentEnrollmentRepository = Depends(get_agent_enrollment_repo),
    session: AsyncSession = Depends(get_session),
):
    """Revoke an agent immediately (``revoked_at = now``, no grace)."""
    enrollment = await repo.get_by_id(agent_id, org.id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await agent_token.revoke(repo, enrollment)
    await _audit_safe(
        session,
        actor=current_user,
        org_id=org.id,
        action="agent.revoke",
        payload={"agent_id": agent_id},
    )
    return None


async def _audit_safe(
    session: AsyncSession,
    *,
    actor: User,
    org_id: int,
    action: str,
    payload: dict,
) -> None:
    """Audit best-effort: the token mutation already committed via the repo, so
    an audit failure must not surface as a 500 or undo the credential change."""
    try:
        await _audit(session, actor=actor, org_id=org_id, action=action, payload=payload)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for %s (org %s)", action, org_id)
