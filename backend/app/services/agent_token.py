"""Agent bearer-token service (Month 4 Phase 1).

Issues, verifies, rotates, and revokes the per-host scanner credential. The
trust model is frozen in ``docs/month_4_phase0_closeout.md`` Step 2; this module
is its enforcement point. All DB access goes through
``SqlAgentEnrollmentRepository`` — this service never touches SQLAlchemy directly.

Token format: ``ht_<prefix>_<secret>``.
  * ``prefix`` is a public lookup handle (stored as ``token_prefix``).
  * ``secret`` is the bearer proof; only ``sha256(secret)`` is stored.

The raw token is returned exactly once at issue/rotate time and is never
retrievable again — losing it means re-issuing, matching SSH key / PAT behavior.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.agent_enrollment import AgentEnrollment
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository

TOKEN_NAMESPACE = "ht"
# 8 hex chars = 32 bits of prefix space; unique constraint + retry guards the
# astronomically rare collision.
_PREFIX_BYTES = 4
# 256 bits of secret entropy.
_SECRET_BYTES = 32
_PREFIX_COLLISION_RETRIES = 5


@dataclass(frozen=True)
class IssuedToken:
    """Result of issuing/rotating: the persisted row plus the one-time raw token."""

    enrollment: AgentEnrollment
    raw_token: str


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_token() -> tuple[str, str, str]:
    """Return ``(raw_token, prefix, token_hash)`` for a fresh credential."""
    prefix = secrets.token_hex(_PREFIX_BYTES)
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    raw_token = f"{TOKEN_NAMESPACE}_{prefix}_{secret}"
    return raw_token, prefix, _hash_secret(secret)


def _parse_token(raw_token: str) -> tuple[str, str] | None:
    """Split ``ht_<prefix>_<secret>`` → ``(prefix, secret)``; None if malformed.

    ``maxsplit=2`` keeps the secret intact even though ``token_urlsafe`` can emit
    ``_`` characters. The prefix is pure hex, so it never contains ``_``.
    """
    parts = raw_token.split("_", 2)
    if len(parts) != 3 or parts[0] != TOKEN_NAMESPACE:
        return None
    _, prefix, secret = parts
    if not prefix or not secret:
        return None
    return prefix, secret


def _default_expiry(now: datetime) -> datetime:
    return now + timedelta(days=settings.AGENT_TOKEN_DEFAULT_EXPIRY_DAYS)


async def issue(
    repo: SqlAgentEnrollmentRepository,
    *,
    org_id: int,
    name: str,
    scopes: list[str] | None,
    created_by_user_id: int | None,
    expires_at: datetime | None = None,
    now: datetime | None = None,
) -> IssuedToken:
    """Mint a new per-agent credential and persist hash-only.

    Retries on the (vanishingly unlikely) prefix collision rather than failing
    the caller.
    """
    now = now or datetime.now(UTC)
    expires_at = expires_at or _default_expiry(now)

    last_error: Exception | None = None
    for _ in range(_PREFIX_COLLISION_RETRIES):
        raw_token, prefix, token_hash = _generate_token()
        if await repo.get_by_prefix(prefix) is not None:
            continue  # collision — try a fresh prefix
        try:
            enrollment = await repo.create(
                org_id,
                name=name,
                token_hash=token_hash,
                token_prefix=prefix,
                scopes=scopes,
                created_by_user_id=created_by_user_id,
                expires_at=expires_at,
            )
        except IntegrityError as exc:  # pragma: no cover - race on the unique index
            last_error = exc
            continue
        return IssuedToken(enrollment=enrollment, raw_token=raw_token)

    raise RuntimeError("Could not issue agent token: prefix collision retries exhausted") from (
        last_error
    )


async def verify(
    repo: SqlAgentEnrollmentRepository,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> AgentEnrollment | None:
    """Resolve and validate a raw bearer token; bump ``last_used_at`` on success.

    Returns the enrollment if the token is genuine and currently usable, else
    ``None``. Rejects revoked (``revoked_at <= now``) and expired tokens; accepts
    a token still inside its rotation grace window (``revoked_at > now``).
    """
    now = now or datetime.now(UTC)

    parsed = _parse_token(raw_token)
    if parsed is None:
        return None
    prefix, secret = parsed

    enrollment = await repo.get_by_prefix(prefix)
    if enrollment is None:
        return None

    # Constant-time compare so a timing side-channel can't probe the hash.
    if not hmac.compare_digest(_hash_secret(secret), enrollment.token_hash):
        return None

    if enrollment.revoked_at is not None and _as_aware(enrollment.revoked_at) <= now:
        return None
    if enrollment.expires_at is not None and _as_aware(enrollment.expires_at) <= now:
        return None

    await repo.touch_last_used(enrollment, now)
    return enrollment


async def rotate(
    repo: SqlAgentEnrollmentRepository,
    enrollment: AgentEnrollment,
    *,
    created_by_user_id: int | None,
    now: datetime | None = None,
) -> IssuedToken:
    """Issue a replacement credential and grace-expire the old one.

    The new token is a fresh row (its own prefix/secret) carrying over the
    agent's name and scopes. The old row's ``revoked_at`` is set to
    ``now + grace`` so its token keeps working for the configured window — a
    live host can pick up the new token before the old one dies.
    """
    now = now or datetime.now(UTC)
    grace_until = now + timedelta(hours=settings.AGENT_TOKEN_ROTATION_GRACE_HOURS)

    issued = await issue(
        repo,
        org_id=enrollment.org_id,
        name=enrollment.name,
        scopes=enrollment.scopes,
        created_by_user_id=created_by_user_id,
        now=now,
    )
    await repo.set_revoked_at(enrollment, grace_until)
    return issued


async def revoke(
    repo: SqlAgentEnrollmentRepository,
    enrollment: AgentEnrollment,
    *,
    now: datetime | None = None,
) -> AgentEnrollment:
    """Revoke immediately by setting ``revoked_at = now`` (no grace)."""
    now = now or datetime.now(UTC)
    return await repo.set_revoked_at(enrollment, now)


def _as_aware(value: datetime) -> datetime:
    """Treat naive timestamps (some DB drivers return them) as UTC for comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
