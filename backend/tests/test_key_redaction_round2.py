"""Follow-up leak paths: Sentry breadcrumbs/locals, NVD query keys, exception chains."""

from __future__ import annotations

import logging
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from app.api.routes.v1 import economics
from app.core.config import settings
from app.core.observability import _before_send, _scrub, init_sentry
from app.ingestors import econ
from app.repositories import exploited_vuln

KEY = "FAKEKEY-ROUND2-987654321"
_RealAsyncClient = httpx.AsyncClient


@pytest.fixture
def sentry_events(monkeypatch):
    events: list[dict] = []

    class _Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.type in ("event", "transaction"):
                    events.append(item.payload.json)

    real_init = sentry_sdk.init
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: real_init(transport=_Capture(), **kw))
    assert init_sentry() is True
    try:
        yield events
    finally:
        monkeypatch.undo()
        sentry_sdk.init(dsn="")


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, request=request)


async def _keyed_request() -> None:
    params = {"get": "ESTAB", "key": KEY}
    async with _RealAsyncClient(transport=httpx.MockTransport(_handler)) as client:
        response = await client.get("https://api.census.gov/data/2022/cbp", params=params)
        response.raise_for_status()


# --- 1: breadcrumbs / transactions ---------------------------------------------------


async def test_sentry_event_breadcrumbs_omit_key(sentry_events):
    try:
        await _keyed_request()
    except httpx.HTTPError:
        logging.getLogger("probe").error("census failed")
    sentry_sdk.flush()
    assert sentry_events
    assert KEY not in repr(sentry_events)


def test_scrub_redacts_bare_http_query_key():
    out = _scrub({"data": {"http.query": f"get=ESTAB&key={KEY}", "http.fragment": "x"}})
    assert KEY not in repr(out)
    assert "get=" in out["data"]["http.query"]


def test_before_breadcrumb_redacts_http_query():
    from app.core.observability import _before_breadcrumb

    crumb = {"category": "httplib", "data": {"url": "https://a/b", "http.query": f"key={KEY}"}}
    out = _before_breadcrumb(crumb, {})
    assert KEY not in repr(out)


def test_before_send_transaction_configured(monkeypatch):
    captured = {}
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    real_init = sentry_sdk.init

    def fake_init(**kw):
        captured.update(kw)
        return real_init(**kw)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    try:
        assert init_sentry() is True
    finally:
        monkeypatch.undo()
        sentry_sdk.init(dsn="")
    assert captured["before_send_transaction"] is _before_send
    assert captured["before_breadcrumb"] is not None
    assert captured["include_local_variables"] is False


# --- 2: frame locals -------------------------------------------------------------------


def test_sentry_exception_frame_locals_omit_key(sentry_events):
    def boom():
        params = {"get": "ESTAB", "key": KEY}  # noqa: F841
        raise RuntimeError("boom")

    try:
        boom()
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()
    assert sentry_events
    assert KEY not in repr(sentry_events)


def test_before_send_strips_frame_vars():
    event = {
        "exception": {
            "values": [{"stacktrace": {"frames": [{"function": "f", "vars": {"p": KEY}}]}}]
        }
    }
    out = _before_send(event, {})
    assert KEY not in repr(out)
    assert "vars" not in out["exception"]["values"][0]["stacktrace"]["frames"][0]


# --- 3: NVD key off the URL --------------------------------------------------------------


def _patch_client(monkeypatch, seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(503, request=request)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(exploited_vuln.httpx, "AsyncClient", factory)


async def test_nvd_enrichment_key_in_header_and_not_logged(caplog, monkeypatch):
    seen: list[httpx.Request] = []
    _patch_client(monkeypatch, seen)
    monkeypatch.setattr(settings, "NVD_API_KEY", KEY)
    exploited_vuln._nvd_enrichment_cache.pop("CVE-2099-0001", None)
    with caplog.at_level(logging.DEBUG):
        await exploited_vuln._fetch_nvd_enrichment("CVE-2099-0001")
    assert seen
    assert KEY not in str(seen[0].url)
    assert seen[0].headers.get("apiKey") == KEY
    assert KEY not in caplog.text
    assert "HTTPStatusError" in caplog.text


async def test_nvd_recent_items_key_in_header_and_not_logged(caplog, monkeypatch):
    seen: list[httpx.Request] = []
    _patch_client(monkeypatch, seen)
    monkeypatch.setattr(settings, "NVD_API_KEY", KEY)
    repo = exploited_vuln.JsonExploitedVulnRepository()
    with caplog.at_level(logging.DEBUG):
        items = await repo._fetch_recent_nvd_risk_items(exclude_ids=set())
    assert items == []
    assert KEY not in str(seen[0].url)
    assert seen[0].headers.get("apiKey") == KEY
    assert KEY not in caplog.text


# --- 4: exception chain ---------------------------------------------------------------------


async def test_census_csv_fallback_failure_does_not_chain_keyed_url(monkeypatch):
    monkeypatch.setattr(settings, "CENSUS_API_KEY", KEY)
    url = f"https://api.census.gov/data/2023/cbp?key={KEY}"

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *a, **k):
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError(
                f"error for url '{url}'",
                request=request,
                response=httpx.Response(503, request=request),
            )

    monkeypatch.setattr(econ.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(
        econ, "ingest_region_economics_from_csv", AsyncMock(side_effect=OSError("csv"))
    )
    with pytest.raises(OSError) as info:
        await econ.ingest_region_economics_from_census(MagicMock())
    text = "".join(
        logging.Formatter().formatException(
            (type(info.value), info.value, info.value.__traceback__)
        )
    )
    assert KEY not in text


# --- 5: ReDoS ---------------------------------------------------------------------------------


def test_scrub_adversarial_question_marks_is_fast():
    payload = "https://h/" + "?" * 100_000
    start = time.perf_counter()
    _scrub(payload)
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("field", ["query_string", "http.query"])
def test_scrub_adversarial_bare_query_is_fast(field):
    start = time.perf_counter()
    _scrub({field: "a" * 100_000})
    assert time.perf_counter() - start < 1.0


def test_scrub_bare_query_keeps_names_and_valueless_pieces():
    out = _scrub({"query_string": f"get=ESTAB&key={KEY}&flag"})
    assert out["query_string"] == "get=[redacted]&key=[redacted]&flag"


# --- 6: non-HTTP errors keep their message ------------------------------------------------------


async def test_bea_cache_value_error_keeps_message(caplog, monkeypatch):
    monkeypatch.setattr(economics, "_BEA_CACHE", None)
    monkeypatch.setattr(economics, "_BEA_CACHE_LOADED", False)
    monkeypatch.setattr(
        economics,
        "_load_census_establishment_counts",
        AsyncMock(side_effect=ValueError("bad payload shape")),
    )
    with caplog.at_level(logging.DEBUG):
        await economics._load_bea_cache()
    assert "bad payload shape" in caplog.text
