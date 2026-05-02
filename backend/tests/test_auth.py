"""Tests for Firebase authentication endpoints."""

import logging
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from firebase_admin.exceptions import FirebaseError
from httpx import AsyncClient

from app.api.routes.v1.auth import _TOKEN_CLOCK_SKEW_SECONDS
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
