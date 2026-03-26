"""Shared FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status

from app.api.routes.v1.auth import get_current_user
from app.db.user import User

# Maps role names to a numeric level so hierarchy comparisons are simple.
_ROLE_LEVELS: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
}


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
