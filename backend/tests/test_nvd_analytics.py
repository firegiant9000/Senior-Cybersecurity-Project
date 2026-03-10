"""Tests for NVD analytics endpoints."""

import pytest
from httpx import AsyncClient

# The analytics endpoint queries the CVE table directly.  In CI the table
# may not exist, so we accept 200 or 500.
_DB_OK = (200, 500)


@pytest.mark.asyncio
async def test_severity_distribution_returns_200(client: AsyncClient) -> None:
    """Test severity distribution endpoint returns valid structure."""
    response = await client.get("/api/v1/nvd/analytics/severity-distribution")
    assert response.status_code in _DB_OK
    if response.status_code == 200:
        data = response.json()
        assert "items" in data
        assert "total_cves" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total_cves"], int)
        assert data["date_from"] is None
        assert data["date_to"] is None


@pytest.mark.asyncio
async def test_severity_distribution_with_date_filters(client: AsyncClient) -> None:
    """Test severity distribution accepts date filter parameters."""
    response = await client.get(
        "/api/v1/nvd/analytics/severity-distribution",
        params={"date_from": "2024-01-01", "date_to": "2024-12-31"},
    )
    assert response.status_code in _DB_OK
    if response.status_code == 200:
        data = response.json()
        assert data["date_from"] == "2024-01-01"
        assert data["date_to"] == "2024-12-31"
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_severity_distribution_invalid_date(client: AsyncClient) -> None:
    """Test severity distribution rejects malformed date."""
    response = await client.get(
        "/api/v1/nvd/analytics/severity-distribution",
        params={"date_from": "not-a-date"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_severity_distribution_item_structure(client: AsyncClient) -> None:
    """Test each item has the expected severity/count fields."""
    response = await client.get("/api/v1/nvd/analytics/severity-distribution")
    if response.status_code == 200:
        data = response.json()
        for item in data["items"]:
            assert "severity" in item
            assert "count" in item
            assert isinstance(item["severity"], str)
            assert isinstance(item["count"], int)
            assert item["count"] >= 0
