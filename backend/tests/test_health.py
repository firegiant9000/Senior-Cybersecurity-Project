"""Tests for health check endpoints."""

import re

import pytest
from httpx import AsyncClient

KNOWN_ENVIRONMENTS = {"development", "staging", "production", "test", "testing", "local"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")


def _assert_health_body(data):
    assert data["status"] == "ok"
    assert isinstance(data["service"], str) and data["service"]
    assert SEMVER_RE.match(data["version"]), f"version {data['version']!r} does not match semver"
    assert data["environment"] in KNOWN_ENVIRONMENTS, (
        f"unexpected environment {data['environment']!r}"
    )


@pytest.mark.asyncio
async def test_health_root(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_v1(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_root_unauthenticated(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_v1_unauthenticated(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/v1/health")
    assert response.status_code == 200
    _assert_health_body(response.json())
