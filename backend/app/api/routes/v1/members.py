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
from app.core.dependencies import (
    require_membership_role,
    require_same_org_membership,
)
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.enums import OrgRole
from app.db.membership import Membership
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


@router.post("/orgs/{org_id}/invites", response_model=InviteRead, status_code=201)
@router.post("/organizations/{org_id}/invites", response_model=InviteRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_invite(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: InviteCreate,
    current_user: User = Depends(get_current_user),
    _membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Create a pending invite for the given email.

    Requires org admin/owner role. Owner role needed to invite as admin.
    """
    if body.role == OrgRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot invite as owner")

    await repo.expire_stale()
    existing = await repo.get_active_membership_by_email(org_id=org_id, email=str(body.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already an active org member")

    try:
        invite = await repo.create(
            org_id=org_id,
            invited_email=str(body.email),
            org_role=str(body.role),
            invited_by=current_user.id,
        )
    except IntegrityError:
        await session.rollback()
        logger.warning("Duplicate invite attempt for %s in org %s", body.email, org_id)
        raise HTTPException(
            status_code=409, detail="A pending invite for this email already exists"
        )

    return invite


@router.get(
    "/orgs/{org_id}/invites",
    response_model=InviteListResponse,
)
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
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    _membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """List invites for an organization. Requires org admin/owner."""
    items, total = await repo.list_by_org(org_id, page, page_size)
    return InviteListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[InviteRead.model_validate(i) for i in items],
    )


@router.delete(
    "/orgs/{org_id}/invites/{invite_id}",
    status_code=204,
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
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    _membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """Revoke a pending invite. Requires org admin/owner."""
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
        token=invite.token,
        org_name=org_name,
        role=invite.role,
        email=invite.email,
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

    The authenticated user's email must match the invite and be pending.
    """
    async with session.begin():
        invite = await repo.get_by_token_for_update(token)
        if invite is None or invite.status != "pending":
            raise HTTPException(status_code=404, detail="Invite not found or no longer valid")
        if invite.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=410, detail="Invite has expired")
        if invite.email.lower() != current_user.email.lower():
            raise HTTPException(
                status_code=403, detail="This invite was sent to a different email address"
            )

        existing_membership = await repo.get_active_membership(current_user.id, invite.org_id)
        if existing_membership is not None:
            raise HTTPException(status_code=409, detail="You are already a member of this org")

        await repo.create_membership(current_user.id, invite.org_id, invite.role)
        # Keep legacy single-org fields in sync for existing endpoints.
        if current_user.org_id is None:
            current_user.org_id = invite.org_id
            current_user.org_role = invite.role
            session.add(current_user)
        await repo.mark_accepted(invite)

    return {"detail": "Invite accepted", "org_id": invite.org_id}


# ── Member endpoints ──────────────────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/members",
    response_model=MemberListResponse,
)
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
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    _membership: Membership = Depends(require_same_org_membership),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """List members of an organization. Any org member can view."""
    items, total = await repo.list_members_with_users(org_id, page, page_size)
    return MemberListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            MemberRead(
                user_id=membership.user_id,
                email=user.email,
                role=membership.role,
                status=membership.status,
                is_active=user.is_active,
            )
            for membership, user in items
        ],
    )


@router.patch(
    "/orgs/{org_id}/members/{user_id}",
    response_model=MemberRead,
)
@router.patch(
    "/organizations/{org_id}/members/{user_id}",
    response_model=MemberRead,
)
@router.put(
    "/orgs/{org_id}/members/{user_id}",
    response_model=MemberRead,
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
    current_user: User = Depends(get_current_user),
    current_membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """Update a member's org role. Requires admin/owner role."""

    if body.role == OrgRole.OWNER:
        raise HTTPException(
            status_code=400, detail="Cannot assign owner role through this endpoint"
        )
    member = await repo.get_member(user_id, org_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == OrgRole.OWNER and body.role != OrgRole.OWNER:
        owners = await repo.count_active_owners(org_id)
        if owners <= 1:
            if user_id == current_user.id and current_membership.role == OrgRole.OWNER:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote yourself as the last organization owner",
                )
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last organization owner",
            )

    updated = await repo.update_member_role(member, str(body.role))
    user = await repo.get_user(updated.user_id)
    if user is not None and user.org_id == org_id:
        user.org_role = updated.role
        session.add(user)
        await session.commit()
    return MemberRead(
        user_id=updated.user_id,
        email=user.email if user else "",
        role=updated.role,
        status=updated.status,
        is_active=user.is_active if user else False,
    )


@router.delete(
    "/orgs/{org_id}/members/{user_id}",
    status_code=204,
)
@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=204,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def remove_member(
    request: Request,  # noqa: ARG001
    org_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    _membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """Remove a member from the organization. Requires admin/owner."""
    member = await repo.get_member(user_id, org_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == OrgRole.OWNER:
        owners = await repo.count_active_owners(org_id)
        if owners <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last organization owner",
            )

    await repo.remove_member(member)
    user = await repo.get_user(member.user_id)
    if user is not None and user.org_id == org_id:
        user.org_id = None
        user.org_role = None
        session.add(user)
        await session.commit()
    return None
