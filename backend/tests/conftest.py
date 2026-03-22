"""Test configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests to share."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client


def unique_email() -> str:
    """Generate a unique email for test isolation."""
    return f"test_{uuid4().hex[:8]}@example.com"
