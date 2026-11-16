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


async def test_fetch_by_id_persistent_503_raises_transient_error(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(monkeypatch, _sequence(httpx.Response(503)))
    with pytest.raises(nvd.NvdTransientError):
        await nvd.fetch_nvd_cve_by_id("CVE-2024-0001")
    assert len(calls) == 4  # first try + 3 retries
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2, 4, 8]


async def test_fetch_by_id_404_still_returns_none(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    _install(monkeypatch, _sequence(httpx.Response(404)))
    assert await nvd.fetch_nvd_cve_by_id("CVE-2024-0001") is None
    sleep_mock.assert_not_awaited()


async def test_fetch_by_id_403_key_fallback_uses_no_retry_budget(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(
        monkeypatch,
        _sequence(httpx.Response(403), httpx.Response(503), httpx.Response(200, json=_CVE_BODY)),
    )
    assert await nvd.fetch_nvd_cve_by_id("CVE-2024-0001", api_key="k") == {"id": "CVE-2024-0001"}
    assert "apiKey" in calls[0].headers
    assert "apiKey" not in calls[1].headers
    assert "apiKey" not in calls[2].headers
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2]


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


async def test_ingest_nvd_persistent_503_raises(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    calls = _install(monkeypatch, _sequence(httpx.Response(503)))
    db = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(nvd.NvdTransientError):
        await nvd.ingest_nvd(db)
    assert len(calls) == nvd.NVD_PAGE_5XX_RETRIES + 1


async def test_ingest_nvd_429_raises(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    _install(monkeypatch, _sequence(httpx.Response(429)))
    db = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(nvd.NvdTransientError):
        await nvd.ingest_nvd(db)


async def test_ingest_nvd_page_retry_budget_resets_after_success(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    page1 = {"vulnerabilities": [{"cve": {"id": "bad"}}], "totalResults": 5000}
    calls = _install(
        monkeypatch,
        _sequence(
            httpx.Response(503),
            httpx.Response(200, json=page1),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json=_EMPTY_PAGE),
        ),
    )
    db = MagicMock()
    db.commit = AsyncMock()
    await nvd.ingest_nvd(db)
    assert len(calls) == 6


async def test_ingest_nvd_keeps_committed_pages_when_later_page_fails(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    page1 = {"vulnerabilities": [{"cve": {"id": "bad"}}], "totalResults": 5000}
    _install(
        monkeypatch,
        _sequence(httpx.Response(200, json=page1), httpx.Response(503)),
    )
    db = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(nvd.NvdTransientError):
        await nvd.ingest_nvd(db)
    assert db.commit.await_count == 1  # page 1 committed before page 2 failed


async def test_ingest_nvd_no_pacing_sleep_before_first_request(
    monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    _install(monkeypatch, _sequence(httpx.Response(200, json=_EMPTY_PAGE)))
    db = MagicMock()
    db.commit = AsyncMock()
    await nvd.ingest_nvd(db)
    sleep_mock.assert_not_awaited()


def _db_with_rows(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


_T = nvd.NvdTransientError("down")


@pytest.mark.parametrize("module", ["nvd", "nvd_cpe"])
async def test_backfill_aborts_after_three_consecutive_transient_failures(
    module: str, monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    from app.ingestors import nvd_cpe

    fetch = AsyncMock(side_effect=_T)
    monkeypatch.setattr(nvd, "fetch_nvd_cve_by_id", fetch)
    monkeypatch.setattr(nvd_cpe, "fetch_nvd_cve_by_id", fetch)
    progress = MagicMock()
    if module == "nvd":
        db = _db_with_rows([MagicMock(cve_id=f"CVE-2024-000{i}") for i in range(5)])
        run = nvd.backfill_missing_nvd_fields_for_existing_cves(db, progress_callback=progress)
    else:
        db = _db_with_rows([f"CVE-2024-000{i}" for i in range(5)])
        run = nvd_cpe.backfill_cpe_configurations(db, progress_callback=progress)
    with pytest.raises(nvd.NvdTransientError):
        await run
    assert fetch.await_count == 3
    db.commit.assert_awaited()
    assert progress.call_args.args[0]["transient_failed"] == 3


@pytest.mark.parametrize("module", ["nvd", "nvd_cpe"])
async def test_backfill_success_resets_consecutive_transient_counter(
    module: str, monkeypatch: pytest.MonkeyPatch, sleep_mock: AsyncMock
) -> None:
    from app.ingestors import nvd_cpe

    # fail, fail, success (404 -> None), fail, fail: never 3 in a row
    fetch = AsyncMock(side_effect=[_T, _T, None, _T, _T])
    monkeypatch.setattr(nvd, "fetch_nvd_cve_by_id", fetch)
    monkeypatch.setattr(nvd_cpe, "fetch_nvd_cve_by_id", fetch)
    if module == "nvd":
        db = _db_with_rows([MagicMock(cve_id=f"CVE-2024-000{i}") for i in range(5)])
        results = await nvd.backfill_missing_nvd_fields_for_existing_cves(db)
    else:
        db = _db_with_rows([f"CVE-2024-000{i}" for i in range(5)])
        results = await nvd_cpe.backfill_cpe_configurations(db)
    assert results["transient_failed"] == 4
    assert results["missing_upstream"] == 1
    assert results["checked"] == 5
