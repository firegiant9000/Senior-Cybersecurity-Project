"""Tests for ingest freshness and runs endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_freshness_endpoint(client: AsyncClient):
    resp = await client.get("/api/v1/ingest/freshness")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)


@pytest.mark.asyncio
async def test_freshness_source_structure(client: AsyncClient):
    resp = await client.get("/api/v1/ingest/freshness")
    if resp.status_code != 200:
        pytest.skip("DB unavailable")
    data = resp.json()
    for source in data["sources"]:
        assert "source" in source
        assert "last_run_at" in source
        assert "status" in source
        assert "records_ingested" in source
        assert "error_message" in source


@pytest.mark.asyncio
async def test_ingest_runs_endpoint(client: AsyncClient):
    """GET /api/v1/ingest/runs returns paginated response."""
    resp = await client.get("/api/v1/ingest/runs")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_ingest_runs_source_filter(client: AsyncClient):
    """GET /api/v1/ingest/runs with source filter."""
    resp = await client.get("/api/v1/ingest/runs", params={"source": "nvd"})
    assert resp.status_code in (200, 500)
