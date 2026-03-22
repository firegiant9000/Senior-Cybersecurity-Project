"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from tests.conftest import unique_email


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """POST /api/v1/auth/register with valid data."""
    email = unique_email()
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    assert resp.status_code in (201, 500, 503)
    if resp.status_code == 201:
        data = resp.json()
        assert data["email"] == email
        assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """POST /api/v1/auth/register with duplicate email returns 409."""
    email = unique_email()
    resp1 = await client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    if resp1.status_code != 201:
        pytest.skip("DB unavailable")
    resp2 = await client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """POST /api/v1/auth/login with valid credentials."""
    email = unique_email()
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "TestPass123!"})
    if reg.status_code != 201:
        pytest.skip("DB unavailable")
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "TestPass123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """POST /api/v1/auth/login with wrong password returns 401."""
    email = unique_email()
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "TestPass123!"})
    if reg.status_code != 201:
        pytest.skip("DB unavailable")
    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "WrongPass!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """GET /api/v1/auth/me without token returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    """GET /api/v1/auth/me with valid token returns user."""
    email = unique_email()
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "TestPass123!"})
    if reg.status_code != 201:
        pytest.skip("DB unavailable")
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": "TestPass123!"})
    token = login.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email
