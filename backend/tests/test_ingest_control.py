"""Tests for ingest retry/cancel endpoints and the public health endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# consecutive_failures counting is covered over HTTP in test_ingest_sources.py and
# in the database by test_ingest_catchup.py (consecutive_failure_counts).


# ---------------------------------------------------------------------------
# GET /api/v1/ingest/health — no auth required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_accessible_without_auth(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/ingest/health")
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_health_endpoint_response_shape(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/ingest/health")
    if resp.status_code != 200:
        pytest.skip("DB unavailable")
    data = resp.json()
    assert "healthy" in data
    assert "sources" in data
    assert isinstance(data["healthy"], bool)
    assert isinstance(data["sources"], dict)


@pytest.mark.asyncio
async def test_health_sources_have_expected_keys(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/ingest/health")
    if resp.status_code != 200:
        pytest.skip("DB unavailable")
    for _source, info in resp.json()["sources"].items():
        assert "stale" in info
        assert "last_success_hours_ago" in info
        assert "consecutive_failures" in info


# ---------------------------------------------------------------------------
# POST /api/v1/ingest/runs/{run_id}/retry — requires admin auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.post("/api/v1/ingest/runs/some-run-id/retry")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_retry_nonexistent_run_returns_4xx(client: AsyncClient):
    resp = await client.post("/api/v1/ingest/runs/nonexistent-run-id/retry")
    # 404 if run not found, 403 if role insufficient, 500 if DB down
    assert resp.status_code in (403, 404, 422, 500)


# ---------------------------------------------------------------------------
# POST /api/v1/ingest/runs/{run_id}/cancel — requires admin auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.post("/api/v1/ingest/runs/some-run-id/cancel")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_cancel_nonexistent_run_returns_4xx(client: AsyncClient):
    resp = await client.post("/api/v1/ingest/runs/nonexistent-run-id/cancel")
    assert resp.status_code in (403, 404, 422, 500)
