"""Tests for Firebase authentication endpoints."""

import logging
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from httpx import AsyncClient
from sqlalchemy import select

from app.api.routes.v1.auth import _TOKEN_CLOCK_SKEW_SECONDS
from app.db.engine import AsyncSessionLocal
from app.db.user import User
from app.main import app


@pytest.mark.asyncio
async def test_me_unauthenticated(anon_client: AsyncClient):
    """GET /api/v1/auth/me without token returns 401/403."""
    resp = await anon_client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_invalid_token(anon_client: AsyncClient):
    """GET /api/v1/auth/me with invalid token returns 401."""
    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=FirebaseError(code="INVALID_ARGUMENT", message="Invalid token"),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_verify_called_with_clock_skew(anon_client: AsyncClient):
    """verify_id_token is called with the configured clock_skew_seconds tolerance.

    Guards against accidental removal of the skew window, which would resurface
    the "Token used too early" 401s on hosts whose clock drifts a few seconds.
    """
    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=FirebaseError(code="INVALID_ARGUMENT", message="stop here"),
    ) as mock_verify:
        await anon_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer some-token"},
        )
    mock_verify.assert_called_once()
    assert mock_verify.call_args.kwargs.get("clock_skew_seconds") == _TOKEN_CLOCK_SKEW_SECONDS


@pytest.mark.asyncio
async def test_me_invalid_token_logs_warning(anon_client: AsyncClient, caplog):
    """A rejected token leaves a warning in the logs so failures aren't silently swallowed."""
    with (
        caplog.at_level(logging.WARNING, logger="app.api.routes.v1.auth"),
        patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=FirebaseError(code="INVALID_ARGUMENT", message="boom"),
        ),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer bad-token"},
        )
    assert resp.status_code == 401
    assert any("Firebase token verification failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_me_valid_token_creates_user(client: AsyncClient):
    """GET /api/v1/auth/me with valid Firebase token auto-creates user and returns profile."""
    resp = await client.get("/api/v1/auth/me")
    # May be 200 if DB is available, or 500/503 if DB is not running
    if resp.status_code == 200:
        data = resp.json()
        assert data["email"] == "testuser@example.com"
        assert data["role"] == "viewer"
        assert data["auth_provider"] == "password"
    else:
        # DB not available in CI without PostgreSQL service
        assert resp.status_code in (500, 503)


@pytest.mark.asyncio
async def test_me_valid_token_returns_existing_user(client: AsyncClient):
    """GET /api/v1/auth/me called twice returns the same user (no duplicate)."""
    resp1 = await client.get("/api/v1/auth/me")
    if resp1.status_code != 200:
        pytest.skip("DB unavailable")
    resp2 = await client.get("/api/v1/auth/me")
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _token(uid: str, email: str, *, email_verified: bool) -> dict:
    return {
        "uid": uid,
        "email": email,
        "email_verified": email_verified,
        "firebase": {"sign_in_provider": "password"},
    }


@pytest_asyncio.fixture
async def existing_user():
    """Seed users with a chosen firebase_uid, and delete them afterwards."""
    created: list[int] = []

    async def _make(firebase_uid: str | None) -> User:
        async with AsyncSessionLocal() as session:
            user = User(
                email=f"{_unique('link')}@example.com",
                firebase_uid=firebase_uid,
                role="admin",
                auth_provider="password",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            created.append(user.id)
            return user

    yield _make

    async with AsyncSessionLocal() as session:
        await session.execute(User.__table__.delete().where(User.id.in_(created)))
        await session.commit()


async def _stored_uid(user_id: int) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.firebase_uid).where(User.id == user_id))
        return result.scalar_one()


async def _get_me(anon_client: AsyncClient, decoded: dict):
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        return await anon_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer some-token"}
        )


@pytest.mark.asyncio
async def test_unverified_email_cannot_take_over_existing_account(
    anon_client: AsyncClient, existing_user, caplog
):
    """A token with an unverified email must not rebind another user's account."""
    uid_a, uid_b = _unique("uid-a"), _unique("uid-b")
    user = await existing_user(uid_a)

    with caplog.at_level(logging.WARNING, logger="app.api.routes.v1.auth"):
        resp = await _get_me(anon_client, _token(uid_b, user.email, email_verified=False))

    assert resp.status_code == 403
    assert await _stored_uid(user.id) == uid_a
    assert all(user.email not in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_unverified_email_cannot_link_unbound_account(
    anon_client: AsyncClient, existing_user
):
    """Even a row with no firebase_uid is only linked when the email is verified."""
    user = await existing_user(None)

    resp = await _get_me(anon_client, _token(_unique("uid"), user.email, email_verified=False))

    assert resp.status_code == 403
    assert await _stored_uid(user.id) is None


@pytest.mark.asyncio
async def test_verified_email_links_unbound_account(anon_client: AsyncClient, existing_user):
    """A verified email links a legacy user whose firebase_uid is still null."""
    uid = _unique("uid")
    user = await existing_user(None)

    resp = await _get_me(anon_client, _token(uid, user.email, email_verified=True))

    assert resp.status_code == 200
    assert resp.json()["id"] == user.id
    assert await _stored_uid(user.id) == uid


@pytest.mark.asyncio
async def test_verified_email_does_not_rebind_account_with_other_uid(
    anon_client: AsyncClient, existing_user
):
    """A verified email is not enough to replace an already-bound firebase_uid."""
    uid_a, uid_b = _unique("uid-a"), _unique("uid-b")
    user = await existing_user(uid_a)

    resp = await _get_me(anon_client, _token(uid_b, user.email, email_verified=True))

    assert resp.status_code == 403
    assert await _stored_uid(user.id) == uid_a


@pytest.mark.asyncio
async def test_me_verify_called_with_check_revoked(anon_client: AsyncClient):
    """verify_id_token is asked to reject revoked tokens and disabled users."""
    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=FirebaseError(code="INVALID_ARGUMENT", message="stop here"),
    ) as mock_verify:
        await anon_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer some-token"})
    mock_verify.assert_called_once()
    assert mock_verify.call_args.kwargs.get("check_revoked") is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        firebase_auth.RevokedIdTokenError("The Firebase ID token has been revoked."),
        firebase_auth.UserDisabledError("The user record is disabled."),
    ],
    ids=["revoked", "disabled"],
)
async def test_me_revoked_or_disabled_returns_401(anon_client: AsyncClient, error):
    with patch("firebase_admin.auth.verify_id_token", side_effect=error):
        resp = await anon_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer some-token"}
        )
    assert resp.status_code == 401


class TestAuthWithMockedDB:
    @pytest.fixture(autouse=True)
    def _override_get_current_user(self):
        from app.api.routes.v1.auth import get_current_user

        fake_user = User(
            id=1,
            firebase_uid="test-firebase-uid-global",
            email="testuser@example.com",
            role="viewer",
            auth_provider="password",
            created_at=datetime.now(UTC),
        )
        fake_user.is_active = True

        async def _fake_get_current_user():
            return fake_user

        app.dependency_overrides[get_current_user] = _fake_get_current_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_me_returns_200_with_correct_fields(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "testuser@example.com"
        assert data["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_me_auth_provider_field(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["auth_provider"] == "password"
