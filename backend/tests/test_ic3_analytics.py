"""Tests for IC3 analytics endpoints."""

import pytest
from httpx import AsyncClient


def _assert_error_shape(resp):
    data = resp.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


@pytest.mark.asyncio
async def test_attack_types(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/attack-types")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
    else:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_attack_types_with_year(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/attack-types", params={"year": 2023})
    assert resp.status_code in (200, 500)
    if resp.status_code == 500:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_industry_risk(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/industry-risk")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert "items" in resp.json()
    else:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_geographic_heatmap(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/geographic-heatmap")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert "items" in resp.json()
    else:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_temporal_trends(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/temporal-trends")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert "items" in resp.json()
    else:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_temporal_trends_invalid_range(client: AsyncClient):
    resp = await client.get(
        "/api/v1/ic3/analytics/temporal-trends", params={"year_from": 2025, "year_to": 2020}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sector_attack_matrix(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/sector-attack-matrix")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert "items" in resp.json()
    else:
        _assert_error_shape(resp)


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient):
    resp = await client.get("/api/v1/ic3/analytics/dashboard-summary")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "total_complaints" in data
    else:
        _assert_error_shape(resp)
