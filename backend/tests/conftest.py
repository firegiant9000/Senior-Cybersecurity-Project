"""Test configuration and fixtures."""

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
