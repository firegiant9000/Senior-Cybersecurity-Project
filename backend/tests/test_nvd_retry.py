"""NVD transient-failure retries (5xx / transport errors) and request pacing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import get_settings
from app.ingestors import nvd

_RealAsyncClient = httpx.AsyncClient

_CVE_BODY = {"vulnerabilities": [{"cve": {"id": "CVE-2024-0001"}}]}
_EMPTY_PAGE = {"vulnerabilities": [], "totalResults": 0}


def _install(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> list[httpx.Request]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(wrapped)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return calls


def _sequence(*responses: httpx.Response | Exception) -> Callable[[httpx.Request], httpx.Response]:
    items = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        item = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(item, Exception):
            raise item
        return item

    return handler


@pytest.fixture
def sleep_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mock)
    monkeypatch.setattr(get_settings(), "NVD_API_KEY", "")
    return mock


def test_request_delay_helper() -> None:
    assert nvd.nvd_request_delay_seconds(None) == 6.0
    assert nvd.nvd_request_delay_seconds("") == 6.0
    assert nvd.nvd_request_delay_seconds("key") == 1.2


async def test_fetch_by_id_retries_503_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(
        monkeypatch,
        _sequence(httpx.Response(503), httpx.Response(503), httpx.Response(200, json=_CVE_BODY)),
    )
    assert await nvd.fetch_nvd_cve_by_id("CVE-2024-0001") == {"id": "CVE-2024-0001"}
    assert len(calls) == 3
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2, 4]


async def test_fetch_by_id_persistent_503_returns_none(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(monkeypatch, _sequence(httpx.Response(503)))
    assert await nvd.fetch_nvd_cve_by_id("CVE-2024-0001") is None
    assert len(calls) == 4  # first try + 3 retries
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2, 4, 8]


async def test_fetch_by_id_retries_transport_error(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(
        monkeypatch,
        _sequence(httpx.ConnectError("boom"), httpx.Response(200, json=_CVE_BODY)),
    )
    assert await nvd.fetch_nvd_cve_by_id("CVE-2024-0001") == {"id": "CVE-2024-0001"}
    assert len(calls) == 2


async def test_fetch_by_id_non_transient_status_still_raises(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    _install(monkeypatch, _sequence(httpx.Response(400)))
    with pytest.raises(httpx.HTTPStatusError):
        await nvd.fetch_nvd_cve_by_id("CVE-2024-0001")
    sleep_mock.assert_not_awaited()


async def test_ingest_nvd_retries_503_page_then_continues(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(
        monkeypatch,
        _sequence(httpx.Response(503), httpx.Response(200, json=_EMPTY_PAGE)),
    )
    db = MagicMock()
    db.commit = AsyncMock()
    assert await nvd.ingest_nvd(db) == 0
    assert len(calls) == 2
    # backoff (2s) then the keyless inter-request delay (6s)
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2, 6.0]


async def test_ingest_nvd_gives_up_on_persistent_503_without_raising(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(monkeypatch, _sequence(httpx.Response(503)))
    db = MagicMock()
    db.commit = AsyncMock()
    assert await nvd.ingest_nvd(db) == 0
    assert len(calls) == nvd.NVD_PAGE_5XX_RETRIES + 1
