"""Rate limiting (slowapi) is wired through the real app and returns the app's 429 shape."""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from starlette.requests import Request

import app.core.limiter as limiter_module
from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import get_current_org
from app.core.limiter import agent_token_key, client_ip, limiter
from app.db.engine import get_session
from app.main import app

# GET /api/v1/organizations/mine/ai-summary is decorated with @limiter.limit("5/minute").
URL = "/api/v1/organizations/mine/ai-summary"


async def _no_session():
    yield None


@pytest_asyncio.fixture
async def limited_client(client: AsyncClient, monkeypatch):
    """The shared client with auth/org/session stubbed and a clean limiter."""
    monkeypatch.setattr(settings, "AI_SUMMARY_ENABLED", False)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="test-user", role="viewer"
    )
    app.dependency_overrides[get_current_org] = lambda: SimpleNamespace(id="test-org")
    app.dependency_overrides[get_session] = _no_session
    limiter.reset()
    try:
        yield client
    finally:
        limiter.reset()
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_ai_summary_rate_limit_returns_429(limited_client: AsyncClient):
    for _ in range(5):
        resp = await limited_client.get(URL)
        assert resp.status_code == 503

    resp = await limited_client.get(URL)
    assert resp.status_code == 429
    assert resp.json() == {"error": "Too Many Requests", "detail": "5 per 1 minute"}
    assert int(resp.headers["Retry-After"]) == 60


def _request(peer: str, xff: str | list[str] | None = None, auth: str | None = None) -> Request:
    headers = []
    for line in [xff] if isinstance(xff, str) else xff or []:
        headers.append((b"x-forwarded-for", line.encode()))
    if auth is not None:
        headers.append((b"authorization", auth.encode()))
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_client_ip_ignores_forwarded_for_by_default(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", False)
    assert client_ip(_request("10.1.2.3", "203.0.113.9")) == "10.1.2.3"


@pytest.mark.parametrize(
    ("xff", "expected"),
    [
        # The proxy appends the address it saw; a client-supplied prefix is ignored.
        ("198.51.100.7, 203.0.113.9", "203.0.113.9"),
        ("203.0.113.9", "203.0.113.9"),
        (" 203.0.113.9 ", "203.0.113.9"),
        # A client-sent first header line cannot pick the key; the last line's
        # rightmost entry (what the proxy added) wins.
        (["198.51.100.7", "203.0.113.9"], "203.0.113.9"),
        (["198.51.100.7", "1.1.1.1, 203.0.113.9"], "203.0.113.9"),
        # IPv6 keys on the /64, so rotating addresses inside one allocation does not
        # get new buckets; IPv4-mapped addresses key as plain IPv4.
        ("1.1.1.1, 2001:db8::1", "2001:db8::/64"),
        ("2001:db8::2", "2001:db8::/64"),
        ("::ffff:203.0.113.9", "203.0.113.9"),
        # Unusable rightmost entry: fall back to the connecting peer.
        ("203.0.113.9:443", "10.1.2.3"),
        ("", "10.1.2.3"),
        ("203.0.113.9, not-an-ip", "10.1.2.3"),
        ("203.0.113.9,", "10.1.2.3"),
    ],
)
def test_client_ip_uses_rightmost_forwarded_for_when_trusted(monkeypatch, xff, expected):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", True)
    assert client_ip(_request("10.1.2.3", xff)) == expected


def test_client_ip_warns_once_on_unparseable_entry(monkeypatch, caplog):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", True)
    monkeypatch.setattr(limiter_module, "_warned_unparseable", False)
    with caplog.at_level("WARNING", logger="app.core.limiter"):
        client_ip(_request("10.1.2.3", "203.0.113.9, 198.51.100.7:443"))
        client_ip(_request("10.1.2.3", "203.0.113.9, 198.51.100.7:443"))
    warnings = [r for r in caplog.records if r.name == "app.core.limiter"]
    assert len(warnings) == 1
    # Count only: no address from the header reaches the log.
    assert "198.51.100.7" not in caplog.text and "203.0.113.9" not in caplog.text


def test_client_ip_without_header_uses_peer(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", True)
    assert client_ip(_request("10.1.2.3")) == "10.1.2.3"


def test_agent_token_key_falls_back_to_client_ip(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", True)
    assert agent_token_key(_request("10.1.2.3", "203.0.113.9", "Bearer junk")) == "203.0.113.9"
    assert agent_token_key(_request("10.1.2.3", "203.0.113.9", "Bearer ht_abc_secret")) == (
        "agent:abc"
    )


def test_limiter_keys_on_client_ip():
    assert limiter._key_func is client_ip


@pytest.mark.asyncio
async def test_public_ingest_health_is_rate_limited(anon_client: AsyncClient):
    # Public, unauthenticated and DB-backed, so it shares RATE_LIMIT_DATA (60/minute).
    # The daily freshness workflow polls it every 120 s, far below the limit.
    limiter.reset()
    try:
        for _ in range(60):
            resp = await anon_client.get("/api/v1/ingest/health")
            assert resp.status_code == 200
        resp = await anon_client.get("/api/v1/ingest/health")
        assert resp.status_code == 429
        assert resp.json() == {"error": "Too Many Requests", "detail": "60 per 1 minute"}
    finally:
        limiter.reset()
