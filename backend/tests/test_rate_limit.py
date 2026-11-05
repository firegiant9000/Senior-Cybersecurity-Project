"""Rate limiting (slowapi) is wired through the real app and returns the app's 429 shape."""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from starlette.requests import Request

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


def _request(peer: str, xff: str | None = None, auth: str | None = None) -> Request:
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
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
        ("1.1.1.1, 2001:db8::1", "2001:db8::1"),
        # Unusable rightmost entry: fall back to the connecting peer.
        ("", "10.1.2.3"),
        ("203.0.113.9, not-an-ip", "10.1.2.3"),
        ("203.0.113.9,", "10.1.2.3"),
    ],
)
def test_client_ip_uses_rightmost_forwarded_for_when_trusted(monkeypatch, xff, expected):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", True)
    assert client_ip(_request("10.1.2.3", xff)) == expected


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
