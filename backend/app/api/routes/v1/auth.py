"""Authentication routes: Firebase token verification."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.organization import Organization
from app.db.user import User
from app.schemas.user import UserRead

logger = logging.getLogger(__name__)

# Tolerate small clock differences between this host and Google's token-issuing
# servers. Without this, a backend clock that's a few seconds ahead of real time
# (common with Docker Desktop on Windows) rejects fresh tokens as "used too early."
_TOKEN_CLOCK_SKEW_SECONDS = 10

router = APIRouter(prefix="/auth", tags=["auth"])
_log = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Verify Firebase ID token and return (or auto-create) the local User."""
    token = credentials.credentials
    try:
        # check_revoked also rejects tokens belonging to disabled Firebase users.
        # RevokedIdTokenError and UserDisabledError are FirebaseErrors -> 401 below.
        decoded = firebase_auth.verify_id_token(
            token, check_revoked=True, clock_skew_seconds=_TOKEN_CLOCK_SKEW_SECONDS
        )
    except (ValueError, FirebaseError) as exc:
        _log.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    firebase_uid: str = decoded["uid"]
    email: str = decoded.get("email", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing email claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up existing user by firebase_uid
    result = await session.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    # Fallback: match by email for users migrating from old auth. Only link a row
    # that has never been bound to a Firebase account, and only when Firebase has
    # verified the caller owns the email address.
    if user is None:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            if decoded.get("email_verified") is not True or user.firebase_uid is not None:
                _log.warning(
                    "Refused to link Firebase account to existing user by email",
                    extra={
                        "user_id": user.id,
                        "email_verified": decoded.get("email_verified") is True,
                        "existing_uid_bound": user.firebase_uid is not None,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unable to link this sign-in to an existing account",
                )
            user.firebase_uid = firebase_uid
            user.auth_provider = decoded.get("firebase", {}).get("sign_in_provider", "email")
            await session.commit()
            await session.refresh(user)

    # Auto-create on first login
    if user is None:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            role="viewer",
            auth_provider=decoded.get("firebase", {}).get("sign_in_provider", "email"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user


@router.get("/me", response_model=UserRead)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Return profile information for the current authenticated user.

    Enriches the response with ``org_is_demo`` so the frontend can render the
    demo banner without making a second request.
    """
    org_is_demo = False
    if current_user.org_id is not None:
        result = await session.execute(
            select(Organization.is_demo).where(Organization.id == current_user.org_id)
        )
        org_is_demo = bool(result.scalar_one_or_none())
    return UserRead.model_validate(current_user, from_attributes=True).model_copy(
        update={"org_is_demo": org_is_demo}
    )
