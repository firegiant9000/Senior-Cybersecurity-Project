"""Tests for the size-capped streaming JSON fetch helper (T-ING-06)."""

import gzip
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.http_fetch import FEED_TIMEOUT, ResponseTooLargeError, get_json_capped

URL = "https://feed.example.test/data.json"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_returns_json_under_cap():
    def handler(request):
        return httpx.Response(200, json={"a": [1, 2, 3]})

    async with _client(handler) as client:
        assert await get_json_capped(client, URL, max_bytes=1024) == {"a": [1, 2, 3]}


async def test_raises_when_streamed_body_exceeds_cap():
    cap = 4096
    consumed = []

    async def body():
        for _ in range(cap // 1024):
            consumed.append(1)
            yield b"x" * 1024
        consumed.append(1)
        yield b"x"
        # Must never be pulled once the cap is exceeded.
        consumed.append(1)
        yield b"y" * 1024

    def handler(request):
        return httpx.Response(200, content=body())

    async with _client(handler) as client:
        with pytest.raises(ResponseTooLargeError) as exc:
            await get_json_capped(client, URL, max_bytes=cap)
    assert len(consumed) == cap // 1024 + 1
    assert "xxxx" not in str(exc.value)


async def test_raises_fast_on_content_length_over_cap():
    pulled = []

    async def body():
        pulled.append(1)
        yield b"{}"

    def handler(request):
        return httpx.Response(200, headers={"Content-Length": "5000"}, content=body())

    async with _client(handler) as client:
        with pytest.raises(ResponseTooLargeError):
            await get_json_capped(client, URL, max_bytes=1000)
    assert pulled == []


async def test_gzip_expansion_counts_decoded_bytes():
    raw = json.dumps({"pad": "a" * 100_000}).encode()
    compressed = gzip.compress(raw)
    cap = 10_000
    assert len(compressed) < cap < len(raw)

    def handler(request):
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=compressed)

    async with _client(handler) as client:
        with pytest.raises(ResponseTooLargeError):
            await get_json_capped(client, URL, max_bytes=cap)


async def test_http_error_status_raises():
    def handler(request):
        return httpx.Response(503, json={"error": "down"})

    async with _client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await get_json_capped(client, URL, max_bytes=1024)


async def test_too_large_error_omits_url_and_body():
    def handler(request):
        return httpx.Response(200, content=b"SECRETBODY" * 100)

    async with _client(handler) as client:
        with pytest.raises(ResponseTooLargeError) as exc:
            await get_json_capped(client, URL + "?apiKey=hunter2", max_bytes=10)
    assert "hunter2" not in str(exc.value)
    assert "SECRETBODY" not in str(exc.value)
    assert "10" in str(exc.value)


async def test_kev_client_has_explicit_timeout():
    from app.ingestors import cisa_kev

    fake_client = MagicMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
    fake_cm.__aexit__ = AsyncMock(return_value=False)
    db = AsyncMock()

    with (
        patch.object(cisa_kev.httpx, "AsyncClient", return_value=fake_cm) as ctor,
        patch.object(
            cisa_kev, "get_json_capped", new=AsyncMock(return_value={"vulnerabilities": []})
        ) as fetch,
    ):
        await cisa_kev.ingest_cisa_kev(db)

    assert ctor.call_args.kwargs["timeout"] is FEED_TIMEOUT
    fetch.assert_awaited_once_with(
        fake_client, cisa_kev.CISA_KEV_URL, max_bytes=cisa_kev.KEV_MAX_BYTES
    )
    assert cisa_kev.KEV_MAX_BYTES == 16 * 1024 * 1024
