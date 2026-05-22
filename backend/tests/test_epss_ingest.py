"""Phase D7 — EPSS ingestor + vendor alias resolution unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ingestors.epss import ingest_epss


class _FakeResult:
    def __init__(self, rows: list[tuple[str]]):
        self._rows = rows

    def all(self) -> list[tuple[str]]:
        return self._rows


def _make_session(cve_ids: list[str]) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_FakeResult([(c,) for c in cve_ids]))
    session.commit = AsyncMock()
    return session


def _httpx_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "http://test"))


@pytest.mark.asyncio
async def test_ingest_epss_no_cves_returns_zero() -> None:
    session = _make_session([])
    count = await ingest_epss(session)
    assert count == 0


@pytest.mark.asyncio
async def test_ingest_epss_writes_scores_and_percentiles() -> None:
    session = _make_session(["CVE-2024-0001", "CVE-2024-0002"])

    async def _fake_get(self, url, **kwargs):  # noqa: ANN001, ARG001
        return _httpx_response(
            {
                "data": [
                    {"cve": "CVE-2024-0001", "epss": "0.42", "percentile": "0.91"},
                    {"cve": "CVE-2024-0002", "epss": "0.01", "percentile": "0.05"},
                ]
            }
        )

    with (
        patch("httpx.AsyncClient.get", new=_fake_get),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        count = await ingest_epss(session)

    assert count == 2
    # Two SELECTs would be reading CVEs (1) + per-row UPDATEs (2) = 3 executes
    assert session.execute.await_count >= 3
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ingest_epss_skips_malformed_scores() -> None:
    session = _make_session(["CVE-2024-0001", "CVE-2024-0002"])

    async def _fake_get(self, url, **kwargs):  # noqa: ANN001, ARG001
        return _httpx_response(
            {
                "data": [
                    {"cve": "CVE-2024-0001", "epss": "not-a-float", "percentile": "0.5"},
                    {"cve": "CVE-2024-0002", "epss": "0.5", "percentile": "bogus"},
                ]
            }
        )

    with (
        patch("httpx.AsyncClient.get", new=_fake_get),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        count = await ingest_epss(session)

    # Only the second CVE has a parseable score; its percentile is dropped (None).
    assert count == 1


@pytest.mark.asyncio
async def test_ingest_epss_swallows_http_errors_and_returns_zero() -> None:
    session = _make_session(["CVE-2024-0001"])

    async def _raise(self, url, **kwargs):  # noqa: ANN001, ARG001
        raise httpx.ConnectError("network down")

    with (
        patch("httpx.AsyncClient.get", new=_raise),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        count = await ingest_epss(session)

    assert count == 0
