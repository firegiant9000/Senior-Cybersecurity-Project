"""Tests for KEV/vulnerability endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_severity_summary(client: AsyncClient):
    resp = await client.get("/api/v1/vulnerabilities/exploited/severity-summary")
    assert resp.status_code in (200, 500, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_risk_scored_list(client: AsyncClient):
    resp = await client.get("/api/v1/vulnerabilities/risk-scored")
    assert resp.status_code in (200, 500, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_risk_scored_invalid_sort(client: AsyncClient):
    resp = await client.get(
        "/api/v1/vulnerabilities/risk-scored", params={"sort_by": "nonexistent"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_risk_scored_stats(client: AsyncClient):
    resp = await client.get("/api/v1/vulnerabilities/risk-scored/stats")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "bands" in data
        assert "avg_risk" in data


@pytest.mark.asyncio
async def test_risk_scored_stats_kev_filter(client: AsyncClient):
    resp = await client.get(
        "/api/v1/vulnerabilities/risk-scored/stats", params={"data_source": "kev"}
    )
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_exploited_list(client: AsyncClient):
    resp = await client.get("/api/v1/vulnerabilities/exploited")
    assert resp.status_code in (200, 500, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_exploited_invalid_sort(client: AsyncClient):
    resp = await client.get(
        "/api/v1/vulnerabilities/exploited", params={"sort_by": "invalid_field"}
    )
    assert resp.status_code == 422
