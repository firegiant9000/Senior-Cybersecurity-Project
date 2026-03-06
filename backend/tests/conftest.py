"""Test configuration and fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client
