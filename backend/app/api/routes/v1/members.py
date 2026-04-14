"""Organization member and invite routes — v1."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access, require_org_role
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.enums import OrgRole
from app.db.organization import Organization
from app.db.user import User
from app.repositories.org_invite import SqlOrgInviteRepository, get_invite_repo
from app.schemas.org_invite import (
    InviteCreate,
    InviteListResponse,
    InviteRead,
    InviteTokenRead,
    MemberListResponse,
    MemberRead,
    MemberUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Invite endpoints ──────────────────────────────────────────────────────────


@router.post(
    "/organizations/{org_id}/invites",
    response_model=InviteRead,
    status_code=201,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_invite(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: InviteCreate,
    current_user: User = Depends(require_org_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Create a pending invite for the given email.

    Requires org admin/owner role. Owner role needed to invite as admin.
    """
    await check_org_access(current_user, org_id, session)

    if body.org_role == OrgRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot invite as owner")
    if (
        body.org_role == OrgRole.ADMIN
        and current_user.org_role != OrgRole.OWNER
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Only owners can invite admins")

    try:
        invite = await repo.create(
            org_id=org_id,
            invited_email=str(body.email),
            org_role=str(body.org_role),
            invited_by=current_user.id,
        )
    except IntegrityError:
        logger.warning("Duplicate invite attempt for %s in org %s", body.email, org_id)
        raise HTTPException(
            status_code=409, detail="A pending invite for this email already exists"
        )

    return invite


@router.get(
    "/organizations/{org_id}/invites",
    response_model=InviteListResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_invites(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(require_org_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """List invites for an organization. Requires org admin/owner."""
    await check_org_access(current_user, org_id, session)
    items, total = await repo.list_by_org(org_id, page, page_size)
    return InviteListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[InviteRead.model_validate(i) for i in items],
    )


@router.delete(
    "/organizations/{org_id}/invites/{invite_id}",
    status_code=204,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def revoke_invite(
    request: Request,  # noqa: ARG001
    org_id: int,
    invite_id: int,
    current_user: User = Depends(require_org_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Revoke a pending invite. Requires org admin/owner."""
    await check_org_access(current_user, org_id, session)
    revoked = await repo.revoke(invite_id, org_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    return None


@router.get("/invites/{token}", response_model=InviteTokenRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_invite_by_token(
    request: Request,  # noqa: ARG001
    token: str,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Look up invite details by token. Authenticated users only."""
    invite = await repo.get_by_token(token)
    if invite is None or invite.status != "pending":
        raise HTTPException(status_code=404, detail="Invite not found or no longer valid")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invite has expired")

    result = await session.execute(
        select(Organization.name).where(Organization.id == invite.org_id)
    )
    org_name = result.scalar_one_or_none() or "Unknown"

    return InviteTokenRead(
        invite_token=invite.invite_token,
        org_name=org_name,
        org_role=invite.org_role,
        invited_email=invite.invited_email,
        expires_at=invite.expires_at,
    )


@router.post("/invites/{token}/accept", status_code=200)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def accept_invite(
    request: Request,  # noqa: ARG001
    token: str,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Accept a pending invite and join the organization.

    The authenticated user's email must match the invite, and they must
    not already belong to an organization.
    """
    invite = await repo.get_by_token(token)
    if invite is None or invite.status != "pending":
        raise HTTPException(status_code=404, detail="Invite not found or no longer valid")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invite has expired")
    if invite.invited_email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=403, detail="This invite was sent to a different email address"
        )

    # Lock user row to prevent race with concurrent accept
    result = await session.execute(select(User).where(User.id == current_user.id).with_for_update())
    locked_user = result.scalar_one()

    if locked_user.org_id is not None:
        raise HTTPException(status_code=409, detail="You already belong to an organization")

    locked_user.org_id = invite.org_id
    locked_user.org_role = invite.org_role
    await repo.mark_accepted(invite)

    return {"detail": "Invite accepted", "org_id": invite.org_id}


# ── Member endpoints ──────────────────────────────────────────────────────────


@router.get(
    "/organizations/{org_id}/members",
    response_model=MemberListResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_members(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(require_org_role("member")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """List members of an organization. Any org member can view."""
    await check_org_access(current_user, org_id, session)
    items, total = await repo.list_members(org_id, page, page_size)
    return MemberListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[MemberRead.model_validate(m) for m in items],
    )


@router.put(
    "/organizations/{org_id}/members/{user_id}",
    response_model=MemberRead,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def update_member_role(
    request: Request,  # noqa: ARG001
    org_id: int,
    user_id: int,
    body: MemberUpdate,
    current_user: User = Depends(require_org_role("owner")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Update a member's org role. Requires owner role."""
    await check_org_access(current_user, org_id, session)

    if body.org_role == OrgRole.OWNER:
        raise HTTPException(
            status_code=400, detail="Cannot assign owner role through this endpoint"
        )
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    member = await repo.get_member(user_id, org_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    updated = await repo.update_member_role(member, str(body.org_role))
    return MemberRead.model_validate(updated)


@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=204,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def remove_member(
    request: Request,  # noqa: ARG001
    org_id: int,
    user_id: int,
    current_user: User = Depends(require_org_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Remove a member from the organization. Requires admin/owner."""
    await check_org_access(current_user, org_id, session)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    member = await repo.get_member(user_id, org_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.org_role == OrgRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot remove the organization owner")

    await repo.remove_member(member)
    return None
