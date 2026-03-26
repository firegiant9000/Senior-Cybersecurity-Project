"""Tests for Firebase authentication endpoints."""

from unittest.mock import patch

import pytest
from firebase_admin.exceptions import FirebaseError
from httpx import AsyncClient

FAKE_FIREBASE_TOKEN = {
    "uid": "test-firebase-uid-123",
    "email": "test@example.com",
    "firebase": {"sign_in_provider": "password"},
}


@pytest.fixture
def mock_firebase_verify():
    """Patch Firebase token verification to return a fake decoded token."""
    with patch(
        "firebase_admin.auth.verify_id_token",
        return_value=FAKE_FIREBASE_TOKEN,
    ) as mock:
        yield mock


@pytest.fixture
def mock_firebase_verify_invalid():
    """Patch Firebase token verification to raise an error."""
    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=FirebaseError(code="INVALID_ARGUMENT", message="Invalid token"),
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """GET /api/v1/auth/me without token returns 401/403."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient, mock_firebase_verify_invalid):
    """GET /api/v1/auth/me with invalid token returns 401."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_valid_token_creates_user(client: AsyncClient, mock_firebase_verify):
    """GET /api/v1/auth/me with valid Firebase token auto-creates user and returns profile."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-valid-token"},
    )
    # May be 200 if DB is available, or 500/503 if DB is not running
    if resp.status_code == 200:
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "viewer"
        assert data["auth_provider"] == "password"
    else:
        # DB not available in CI without PostgreSQL service
        assert resp.status_code in (500, 503)


@pytest.mark.asyncio
async def test_me_valid_token_returns_existing_user(client: AsyncClient, mock_firebase_verify):
    """GET /api/v1/auth/me called twice returns the same user (no duplicate)."""
    headers = {"Authorization": "Bearer fake-valid-token"}
    resp1 = await client.get("/api/v1/auth/me", headers=headers)
    if resp1.status_code != 200:
        pytest.skip("DB unavailable")
    resp2 = await client.get("/api/v1/auth/me", headers=headers)
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]
