"""Authentication routes: Firebase token verification."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Verify Firebase ID token and return (or auto-create) the local User."""
    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token)
    except (
        ValueError,
        firebase_auth.InvalidIdTokenError,
        firebase_auth.ExpiredIdTokenError,
        firebase_auth.CertificateFetchError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid: str = decoded["uid"]
    email: str = decoded.get("email", "")

    # Look up existing user by firebase_uid
    result = await session.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

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
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return profile information for the current authenticated user."""
    return current_user
