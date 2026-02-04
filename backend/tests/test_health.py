"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_root(client: AsyncClient) -> None:
    """Test root health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_v1(client: AsyncClient) -> None:
    """Test versioned health endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "environment" in data
