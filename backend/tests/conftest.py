"""Test configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Patch Firebase init before importing the app so it doesn't require credentials
with patch("app.core.firebase.init_firebase"):
    from app.main import app

FAKE_FIREBASE_TOKEN = {
    "uid": "test-firebase-uid-global",
    "email": "testuser@example.com",
    "firebase": {"sign_in_provider": "password"},
}


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests to share."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _mock_firebase_verify():
    """Auto-mock Firebase token verification for all tests.

    This allows protected routes to accept any Bearer token.
    Individual tests can override this with their own mock.
    """
    with patch(
        "firebase_admin.auth.verify_id_token",
        return_value=FAKE_FIREBASE_TOKEN,
    ):
        yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client with a default auth header."""
    headers = {"Authorization": "Bearer fake-test-token"}
    async with AsyncClient(app=app, base_url="http://test", headers=headers) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client without auth headers (for testing 401/403)."""
    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client


def unique_email() -> str:
    """Generate a unique email for test isolation."""
    return f"test_{uuid4().hex[:8]}@example.com"
