"""Shared FastAPI dependencies for authentication and authorization."""

import functools

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import get_session
from app.db.membership import Membership
from app.db.organization import Organization
from app.db.user import User
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token

# Maps role names to a numeric level so hierarchy comparisons are simple.
_ROLE_LEVELS: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
}


# Agent auth is a deliberately separate scheme from ``get_current_user``. A
# Firebase ID token fed here fails to parse as ``ht_<prefix>_<secret>`` (401),
# and an agent token fed to a human route fails Firebase verification (401), so
# the two credential types can never satisfy each other's routes.
_agent_bearer_scheme = HTTPBearer(auto_error=True)


async def get_agent_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(_agent_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AgentEnrollment:
    """Authenticate a scanner agent by its bearer token.

    Returns the resolved enrollment (carrying ``org_id`` + ``scopes``) for the
    scan-upload route in Phase 3. The org is derived from the token — the agent
    can never assert an arbitrary org.
    """
    repo = SqlAgentEnrollmentRepository(session)
    enrollment = await agent_token.verify(repo, credentials.credentials)
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return enrollment


@functools.cache
def require_role(minimum_role: str):
    """Return a dependency that enforces a minimum role level.

    Role hierarchy (lowest → highest): viewer < member < admin.

    Usage::

        @router.get("/secret", dependencies=[Depends(require_role("admin"))])
        async def secret_endpoint(): ...

        # Or inject the user object:
        async def endpoint(user: User = Depends(require_role("member"))): ...
    """
    min_level = _ROLE_LEVELS[minimum_role]

    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if _ROLE_LEVELS.get(current_user.role, -1) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role


async def get_current_org_optional(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Organization | None:
    """Return the caller's organisation, or None if they aren't attached to one.

    Used by repositories that need to vary behaviour based on
    ``organization.is_demo`` without forcing every caller to belong to an
    organisation (global admins, onboarding flows, etc.).
    """
    if current_user.org_id is None:
        return None
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    return result.scalar_one_or_none()


async def get_current_org(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Organization:
    """Return the organization for the current user, or 403 if none."""
    if current_user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization",
        )
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found",
        )
    return org


_ORG_ROLE_LEVELS: dict[str, int] = {
    "member": 0,
    "admin": 1,
    "owner": 2,
}


@functools.cache
def require_org_role(minimum_role: str):
    """Return a dependency that enforces a minimum org-level role.

    Org role hierarchy: member < admin < owner.
    Global admins bypass this check.
    """
    min_level = _ORG_ROLE_LEVELS[minimum_role]

    async def _check_org_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "admin":
            return current_user
        if current_user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with an organization",
            )
        user_level = _ORG_ROLE_LEVELS.get(current_user.org_role or "", -1)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organization role",
            )
        return current_user

    return _check_org_role


async def check_org_access(current_user: User, org_id: int, session: AsyncSession) -> None:
    """Raise 403/404 if user can't access the org or the org doesn't exist.

    Global admins are allowed to access any organization's data by design.
    """
    if current_user.role != "admin" and current_user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


def require_org_or_admin():
    """Return a dependency that resolves the user's org or allows global admins through.

    Non-admin users must belong to an organization (403 otherwise).
    Global admins get their org if they have one, or ``None`` to indicate
    unrestricted access.
    """

    async def _check(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> Organization | None:
        if current_user.role == "admin":
            if current_user.org_id is not None:
                result = await session.execute(
                    select(Organization).where(Organization.id == current_user.org_id)
                )
                return result.scalar_one_or_none()
            return None

        if current_user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with an organization",
            )
        result = await session.execute(
            select(Organization).where(Organization.id == current_user.org_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization not found",
            )
        return org

    return _check


async def require_same_org_membership(
    org_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    """Enforce same-org isolation by requiring an active membership for org_id."""
    membership_result = await session.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.org_id == org_id,
            Membership.status == "active",
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        # Fallback for users who predate the memberships table: if the legacy
        # users.org_id matches, synthesise a membership from the legacy fields
        # so that existing accounts aren't locked out after the migration.
        if current_user.org_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this organization",
            )
        membership = Membership(
            user_id=current_user.id,
            org_id=org_id,
            role=current_user.org_role or "member",
            status="active",
        )
    return membership


@functools.cache
def require_membership_role(minimum_role: str):
    """Return dependency enforcing org role for the requested org_id."""
    min_level = _ORG_ROLE_LEVELS[minimum_role]

    async def _check_role(
        membership: Membership = Depends(require_same_org_membership),
    ) -> Membership:
        membership_level = _ORG_ROLE_LEVELS.get(membership.role, -1)
        if membership_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organization role",
            )
        return membership

    return _check_role
