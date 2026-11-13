"""Tests for RequestContextMiddleware (Month 1 Phase B2).

Guarantees:

1. Every response carries an ``X-Request-ID`` header.
2. Inbound ``X-Request-ID`` is honored (proxies / load tests can correlate).
3. Inbound ``X-Correlation-ID`` is honored as a fallback header name.
4. An inbound id that is not a safe token (control characters, spaces, non-ASCII,
   over-length) is discarded and replaced by a generated id, never truncated.
"""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

_GENERATED_ID_RE = re.compile(r"[0-9a-f]{32}")


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
    """A malicious/buggy client cannot push a 10MB id into our logs.

    Over-length ids are replaced, not truncated: a truncated prefix would still
    be attacker-chosen text.
    """
    rid = "x" * 5000
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": rid},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert _GENERATED_ID_RE.fullmatch(echoed), f"id not replaced (echoed={echoed!r})"


@pytest.mark.asyncio
async def test_request_id_with_crlf_is_replaced(anon_client: AsyncClient):
    """CR/LF in the inbound id must not reach logs as a forged line (T-PLAT-13)."""
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": "abc\r\nFAKE LOG LINE"},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert _GENERATED_ID_RE.fullmatch(echoed), f"id not replaced (echoed={echoed!r})"
    assert "FAKE" not in echoed


@pytest.mark.asyncio
async def test_request_id_with_space_is_replaced(anon_client: AsyncClient):
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": "abc def"},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert _GENERATED_ID_RE.fullmatch(echoed), f"id not replaced (echoed={echoed!r})"


@pytest.mark.asyncio
async def test_request_id_non_ascii_is_replaced(anon_client: AsyncClient):
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": "café-123".encode()},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert _GENERATED_ID_RE.fullmatch(echoed), f"id not replaced (echoed={echoed!r})"


@pytest.mark.asyncio
async def test_request_id_trailing_newline_is_replaced(anon_client: AsyncClient):
    """`$` matches before a trailing newline, so the check must be a full match."""
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": "abc\n"},
    )
    assert resp.status_code == 200
    echoed = resp.headers.get("x-request-id", "")
    assert _GENERATED_ID_RE.fullmatch(echoed), f"id not replaced (echoed={echoed!r})"


@pytest.mark.asyncio
async def test_request_id_valid_uuid_kept(anon_client: AsyncClient):
    rid = "123e4567-e89b-12d3-a456-426614174000"
    resp = await anon_client.get(
        "/api/v1/data-status",
        headers={"X-Request-ID": rid},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == rid
