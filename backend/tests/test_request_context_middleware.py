"""Tests for RequestContextMiddleware (Month 1 Phase B2).

Guarantees:

1. Every response carries an ``X-Request-ID`` header.
2. Inbound ``X-Request-ID`` is honored (proxies / load tests can correlate).
3. Inbound ``X-Correlation-ID`` is honored as a fallback header name.
4. An absurdly long inbound id is truncated rather than blindly trusted.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_response_carries_request_id_header(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/data-status")
    assert resp.status_code == 200
    rid = resp.headers.get("x-request-id")
    assert rid, "response missing X-Request-ID"
    assert len(rid) >= 16, "generated request id looks too short"


@pytest.mark.asyncio
async def test_inbound_request_id_is_echoed(anon_client: AsyncClient):
    rid = "test-trace-abc-123"
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": rid},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == rid


@pytest.mark.asyncio
async def test_inbound_correlation_id_is_accepted(anon_client: AsyncClient):
    rid = "corr-xyz-789"
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Correlation-ID": rid},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == rid


@pytest.mark.asyncio
async def test_inbound_request_id_is_capped(anon_client: AsyncClient):
    """A malicious/buggy client cannot push a 10MB id into our logs."""
    rid = "x" * 5000
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": rid},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert echoed and len(echoed) <= 128, f"id not capped (len={len(echoed)})"
