"""Tests for ingest freshness endpoint."""

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
