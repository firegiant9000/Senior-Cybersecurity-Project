"""T-ING-06: NVD, EPSS and Census fetchers refuse oversized bodies via the shared cap."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import get_settings
from app.core.http_fetch import FeedDeadlineError, ResponseTooLargeError
from app.ingestors import econ, epss, nvd

_RealAsyncClient = httpx.AsyncClient
_CAP = 64
_OVERSIZED = b'{"padding": "' + b"x" * 500 + b'"}'


def _patch_oversized(monkeypatch: pytest.MonkeyPatch, body: bytes = _OVERSIZED) -> None:
    """Route every AsyncClient through a transport that serves ``body`` for any URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, request=request)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_cap_constants_have_the_agreed_values() -> None:
    assert nvd.NVD_PAGE_MAX_BYTES == 64 * 1024 * 1024
    assert nvd.NVD_SINGLE_MAX_BYTES == 2 * 1024 * 1024
    assert epss.EPSS_BATCH_MAX_BYTES == 1024 * 1024
    assert econ.CENSUS_MAX_BYTES == 8 * 1024 * 1024


@pytest.mark.parametrize("fetcher", ["nvd_bulk", "nvd_single", "epss", "census"])
async def test_fetcher_rejects_oversized_body(
    fetcher: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_oversized(monkeypatch)
    monkeypatch.setattr(get_settings(), "NVD_API_KEY", "")
    monkeypatch.setattr(get_settings(), "CENSUS_API_KEY", "")
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    if fetcher == "nvd_bulk":
        monkeypatch.setattr(nvd, "NVD_PAGE_MAX_BYTES", _CAP)
        with pytest.raises(ResponseTooLargeError):
            await nvd.ingest_nvd(MagicMock())
    elif fetcher == "nvd_single":
        monkeypatch.setattr(nvd, "NVD_SINGLE_MAX_BYTES", _CAP)
        with pytest.raises(ResponseTooLargeError):
            await nvd.fetch_nvd_cve_by_id("CVE-2024-0001")
    elif fetcher == "epss":
        monkeypatch.setattr(epss, "EPSS_BATCH_MAX_BYTES", _CAP)
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = [("CVE-2024-0001",)]
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        with caplog.at_level(logging.WARNING):
            assert await epss.ingest_epss(session) == 0
        assert "EPSS batch 0 failed: ResponseTooLargeError" in caplog.text
        session.commit.assert_not_awaited()
    else:
        monkeypatch.setattr(econ, "CENSUS_MAX_BYTES", _CAP)
        upsert = AsyncMock()
        monkeypatch.setattr(econ, "_upsert_economic_indicator", upsert)
        db = MagicMock()
        db.commit = AsyncMock()
        with pytest.raises(RuntimeError, match="Census API error: ResponseTooLargeError"):
            await econ.ingest_region_economics_from_census(db)
        upsert.assert_not_awaited()
        db.commit.assert_not_awaited()


async def test_epss_batch_skipped_on_deadline(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(epss, "get_json_capped", AsyncMock(side_effect=FeedDeadlineError("t")))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = [("CVE-2024-0001",)]
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    with caplog.at_level(logging.WARNING):
        assert await epss.ingest_epss(session) == 0
    assert "EPSS batch 0 failed: FeedDeadlineError" in caplog.text


async def test_census_ingest_fails_on_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "CENSUS_API_KEY", "")
    monkeypatch.setattr(econ, "get_json_capped", AsyncMock(side_effect=FeedDeadlineError("t")))
    db = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(RuntimeError, match="Census API error: FeedDeadlineError"):
        await econ.ingest_region_economics_from_census(db)
    db.commit.assert_not_awaited()


async def test_cve_org_enrichment_oversize_body_is_skipped(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations import cve_org

    _patch_oversized(monkeypatch)
    monkeypatch.setattr(cve_org, "CVE_ORG_MAX_BYTES", _CAP)
    monkeypatch.setattr(cve_org, "_http_client", None)
    cve_org._enrichment_cache.pop("CVE-2099-0001", None)
    try:
        with caplog.at_level(logging.WARNING):
            result = await cve_org.fetch_cve_org_enrichment("CVE-2099-0001")
    finally:
        cve_org._enrichment_cache.pop("CVE-2099-0001", None)
        monkeypatch.setattr(cve_org, "_http_client", None)
    assert result == cve_org.CveOrgEnrichment()
    assert "response body exceeds" in caplog.text


async def test_economics_cache_load_survives_oversize_census_body(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes.v1 import economics

    _patch_oversized(monkeypatch)
    monkeypatch.setattr(economics, "CENSUS_MAX_BYTES", _CAP)
    monkeypatch.setattr(economics, "_BEA_CACHE", None)
    monkeypatch.setattr(economics, "_BEA_CACHE_LOADED", False)
    with caplog.at_level(logging.ERROR):
        assert await economics._load_bea_cache() == []
    assert "response body exceeds" in caplog.text
