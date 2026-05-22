"""Service helpers for the M365 OAuth spike: state tokens + token encryption."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.oauth_state import OAuthState

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
PROVIDER_M365 = "m365"


class M365NotConfigured(RuntimeError):
    """Raised when required M365 settings are missing."""


def require_m365_config() -> None:
    """Raise ``M365NotConfigured`` unless every required setting is present.

    Kept centralised so the consent / callback / sync routes share the same
    pre-flight check and emit the same error.
    """
    missing = [
        name
        for name in ("M365_CLIENT_ID", "M365_CLIENT_SECRET", "M365_REDIRECT_URI", "M365_FERNET_KEY")
        if not getattr(settings, name)
    ]
    if missing:
        raise M365NotConfigured(
            f"M365 integration is not configured (missing: {', '.join(missing)})"
        )


def _fernet() -> Fernet:
    require_m365_config()
    try:
        return Fernet(settings.M365_FERNET_KEY.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise M365NotConfigured(f"M365_FERNET_KEY is malformed: {exc}") from exc


def encrypt_token(token: str | None) -> str | None:
    """Encrypt a token with the configured Fernet key."""
    if token is None:
        return None
    return _fernet().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_token(encrypted: str | None) -> str | None:
    """Decrypt a token previously stored via :func:`encrypt_token`."""
    if encrypted is None:
        return None
    try:
        return _fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        # Almost always means M365_FERNET_KEY was rotated without re-consent.
        raise M365NotConfigured(
            "Stored M365 token cannot be decrypted with the current key — reconnect required."
        ) from exc


async def issue_state_token(
    session: AsyncSession,
    *,
    org_id: int,
    user_id: int,
    redirect_uri: str,
    provider: str = PROVIDER_M365,
) -> OAuthState:
    """Persist and return a fresh OAuth state row.

    Lazily prunes any expired rows for the same (org, user, provider) tuple
    so the table never accumulates dead state across long-lived sessions.
    """
    now = datetime.now(UTC)
    await session.execute(
        delete(OAuthState).where(
            OAuthState.org_id == org_id,
            OAuthState.user_id == user_id,
            OAuthState.provider == provider,
            OAuthState.expires_at < now,
        )
    )
    row = OAuthState(
        org_id=org_id,
        user_id=user_id,
        provider=provider,
        state_token=secrets.token_urlsafe(32),
        redirect_uri=redirect_uri,
        expires_at=now + STATE_TTL,
    )
    session.add(row)
    await session.flush()
    return row


async def consume_state_token(
    session: AsyncSession,
    *,
    state_token: str,
    provider: str = PROVIDER_M365,
) -> OAuthState | None:
    """Look up a state token and delete it in the same call. Returns ``None``
    when the token is missing, mismatched, or already expired (in which case
    the expired row is removed as a side-effect).
    """
    result = await session.execute(
        select(OAuthState).where(
            OAuthState.state_token == state_token,
            OAuthState.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    expired = row.expires_at < datetime.now(UTC)
    await session.execute(delete(OAuthState).where(OAuthState.id == row.id))
    if expired:
        return None
    return row
