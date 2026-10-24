"""API keys travel in URL query strings; they must never reach logs, Sentry or responses."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.api.routes.v1 import economics
from app.core.config import get_settings
from app.core.observability import _before_send, _scrub
from app.ingestors import econ

FAKE_KEY = "FAKEKEY-0123456789abcdef"
CENSUS_URL = f"https://api.census.gov/data/2023/cbp?get=ESTAB&for=state:*&key={FAKE_KEY}"
BEA_URL = f"https://apps.bea.gov/api/data?UserID={FAKE_KEY}&Method=GetData&ResultFormat=JSON"


def _status_error(url: str, status: int = 503) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(
        f"Server error '{status}' for url '{url}'", request=request, response=response
    )


def _connect_error(url: str) -> httpx.ConnectError:
    return httpx.ConnectError(f"connection failed for {url}", request=httpx.Request("GET", url))


# --- _scrub / _before_send ---------------------------------------------------------


def test_scrub_redacts_query_values_in_urls():
    out = _scrub(f"Client error for url '{CENSUS_URL}'")
    assert FAKE_KEY not in out
    assert "api.census.gov/data/2023/cbp" in out
    assert "key=[redacted]" in out
    assert "get=[redacted]" in out


def test_scrub_redacts_bea_userid_and_keeps_fragment():
    out = _scrub(f"see {BEA_URL}#frag")
    assert FAKE_KEY not in out
    assert "UserID=[redacted]" in out
    assert out.endswith("#frag")


def test_scrub_leaves_plain_strings_and_urls_without_query_alone():
    assert _scrub("a=b&c=d") == "a=b&c=d"
    assert _scrub("https://example.com/path") == "https://example.com/path"


def test_scrub_url_redaction_applies_in_nested_structures():
    out = _scrub({"logentry": {"message": f"boom {BEA_URL}"}, "list": [CENSUS_URL]})
    assert FAKE_KEY not in repr(out)


def test_before_send_scrubs_urls_in_event():
    event = {"message": f"BEA failed: {BEA_URL}", "exception": {"values": [{"value": CENSUS_URL}]}}
    out = _before_send(event, {})
    assert out is not None
    assert FAKE_KEY not in repr(out)


# --- economics route ---------------------------------------------------------------


async def test_bea_cache_failure_log_omits_key(caplog, monkeypatch):
    monkeypatch.setattr(economics, "_BEA_CACHE", None)
    monkeypatch.setattr(economics, "_BEA_CACHE_LOADED", False)
    monkeypatch.setattr(
        economics,
        "_load_census_establishment_counts",
        AsyncMock(side_effect=_status_error(CENSUS_URL)),
    )
    with caplog.at_level(logging.DEBUG):
        items = await economics._load_bea_cache()
    assert items == []
    assert FAKE_KEY not in caplog.text
    assert "HTTPStatusError" in caplog.text
    assert "503" in caplog.text


async def test_list_indicators_502_detail_and_log_omit_key(caplog, monkeypatch):
    monkeypatch.setattr(
        economics, "_query_economic_indicators_from_db", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        economics, "_load_bea_cache", AsyncMock(side_effect=_connect_error(BEA_URL))
    )
    request = MagicMock()
    with caplog.at_level(logging.DEBUG), pytest.raises(HTTPException) as exc_info:
        await economics.list_economic_indicators.__wrapped__(
            request,
            page=1,
            page_size=50,
            sort_by="state",
            sort_order="asc",
            search=None,
            db=MagicMock(),
        )
    assert exc_info.value.status_code == 502
    assert FAKE_KEY not in str(exc_info.value.detail)
    assert FAKE_KEY not in caplog.text
    assert "ConnectError" in caplog.text


# --- Census ingestor ---------------------------------------------------------------


async def test_census_ingest_failure_log_omits_key(caplog, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "CENSUS_API_KEY", FAKE_KEY)
    fallback = AsyncMock()
    monkeypatch.setattr(econ, "ingest_region_economics_from_csv", fallback)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *args, **kwargs):
            raise _status_error(CENSUS_URL, 429)

    monkeypatch.setattr(econ.httpx, "AsyncClient", _Client)
    with caplog.at_level(logging.DEBUG):
        await econ.ingest_region_economics_from_census(MagicMock())
    fallback.assert_awaited_once()
    assert FAKE_KEY not in caplog.text
    assert "HTTPStatusError" in caplog.text
    assert "429" in caplog.text
