"""Organization member and invite routes — v1.

Admins manage plain members; granting, changing or removing the admin and owner roles is
owner-only.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import (
    EMAIL_MISMATCH,
    EMAIL_NOT_VERIFIED,
    get_current_user,
    get_token_claims,
)
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

_OWNER_REQUIRED = "Owner role required"


def _require_owner(membership: Membership) -> None:
    """Refuse unless the caller is exactly an owner (a non-standard role fails closed)."""
    if membership.role != OrgRole.OWNER:
        raise HTTPException(status_code=403, detail=_OWNER_REQUIRED)


# ── Invite endpoints ──────────────────────────────────────────────────────────


@router.post("/orgs/{org_id}/invites", response_model=InviteRead, status_code=201)
@router.post("/organizations/{org_id}/invites", response_model=InviteRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_invite(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: InviteCreate,
    current_user: User = Depends(get_current_user),
    current_membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Create a pending invite for the given email.

    Requires org admin; inviting as admin requires owner.
    """
    if body.role == OrgRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot invite as owner")
    if body.role == OrgRole.ADMIN:
        _require_owner(current_membership)

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
    """Revoke a pending invite. Requires org admin; admins may revoke any pending invite."""
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
    claims: dict = Depends(get_token_claims),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),
):
    """Accept a pending invite and join the organization.

    The token's email must be verified and equal the account's email, and the
    account's email must match the invite, which must be pending.
    """
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail=EMAIL_NOT_VERIFIED)
    token_email = claims.get("email") or ""
    account_email = current_user.email or ""
    if not token_email or token_email.lower() != account_email.lower():
        raise HTTPException(status_code=403, detail=EMAIL_MISMATCH)
    # get_current_user's lookups already began a transaction on this session; end it so the
    # explicit begin() below can open the one that holds the invite row lock.
    await session.commit()
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

        # Any status: a removed member keeps an inactive row (UNIQUE user/org), which is
        # reactivated with the invite's role, never the role it had before removal.
        existing_membership = await repo.get_membership_for_update(current_user.id, invite.org_id)
        if existing_membership is not None and existing_membership.status == "active":
            raise HTTPException(status_code=409, detail="You are already a member of this org")

        await repo.activate_membership(
            existing_membership, current_user.id, invite.org_id, invite.role
        )
        # Keep legacy single-org fields in sync for existing endpoints. Conditional on the
        # stored value, so a concurrent accept elsewhere cannot be overwritten from a stale copy.
        await session.execute(
            update(User)
            .where(User.id == current_user.id, User.org_id.is_(None))
            .values(org_id=invite.org_id, org_role=invite.role)
        )
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
                created_at=membership.created_at,
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
    """Update a member's org role.

    Requires org admin for plain members; admins and owners can only be changed by an owner.
    Last-owner protections apply.
    """

    if body.role == OrgRole.OWNER:
        raise HTTPException(
            status_code=400, detail="Cannot assign owner role through this endpoint"
        )
    # The target row and the org's owner rows are locked until the commit below, so the role
    # rule and the last-owner count are decided on rows no concurrent request can change.
    member, owners = await repo.lock_target_and_owners(org_id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    # Allowlist: only a plain member staying a plain member is admin-level. Anything else,
    # including a non-standard stored role, needs an owner.
    if not (member.role == OrgRole.MEMBER and body.role == OrgRole.MEMBER):
        _require_owner(current_membership)
    if member.role == OrgRole.OWNER and body.role != OrgRole.OWNER:
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

    # Legacy field changes ride the same transaction (and lock) as the role change.
    user = await repo.get_user(member.user_id)
    if user is not None and user.org_id == org_id:
        user.org_role = str(body.role)
        session.add(user)
    updated = await repo.update_member_role(member, str(body.role))
    return MemberRead(
        user_id=updated.user_id,
        email=user.email if user else "",
        role=updated.role,
        status=updated.status,
        is_active=user.is_active if user else False,
        created_at=updated.created_at,
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
    current_membership: Membership = Depends(require_membership_role("admin")),
    repo: SqlOrgInviteRepository = Depends(get_invite_repo),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001
):
    """Remove a member from the organization.

    Requires org admin for plain members; admins and owners can only be removed by an owner.
    Last-owner protections apply.
    """
    member, owners = await repo.lock_target_and_owners(org_id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role != OrgRole.MEMBER:
        _require_owner(current_membership)
    if member.role == OrgRole.OWNER and owners <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last organization owner",
        )

    user = await repo.get_user(member.user_id)
    if user is not None and user.org_id == org_id:
        user.org_id = None
        user.org_role = None
        session.add(user)
    await repo.remove_member(member)
    return None
