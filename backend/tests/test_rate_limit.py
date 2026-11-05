"""Rate limiting (slowapi) is wired through the real app and returns the app's 429 shape."""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import get_current_org
from app.core.limiter import limiter
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
