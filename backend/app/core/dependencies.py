"""Shared FastAPI dependencies for authentication and authorization."""

import functools

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.db.engine import get_session
from app.db.organization import Organization
from app.db.user import User

# Maps role names to a numeric level so hierarchy comparisons are simple.
_ROLE_LEVELS: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
}


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
