"""Tests for health check endpoints."""

import asyncio
import re
import time
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.engine import get_health_engine, health_engine
from app.main import app
from app.services import health as health_service
from app.services.health import cached_database_reachable, database_reachable

KNOWN_ENVIRONMENTS = {"development", "staging", "production", "test", "testing", "local"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")


@pytest.fixture(autouse=True)
def _clear_health_cache():
    health_service.reset_cache()
    yield
    health_service.reset_cache()


class _FakeConn:
    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def execute(self, *_args, **_kwargs):
        await asyncio.sleep(self._delay)


class _FakeEngine:
    """Counts connect() calls; execute sleeps ``delay`` seconds."""

    def __init__(self, delay: float = 0.0) -> None:
        self.connects = 0
        self._delay = delay

    def connect(self):
        self.connects += 1

        @asynccontextmanager
        async def _cm():
            yield _FakeConn(self._delay)

        return _cm()


class _HangingEngine:
    def connect(self):
        @asynccontextmanager
        async def _cm():
            await asyncio.sleep(30)
            yield None

        return _cm()


def _assert_health_body(data):
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert isinstance(data["service"], str) and data["service"]
    assert SEMVER_RE.match(data["version"]), f"version {data['version']!r} does not match semver"
    assert data["environment"] in KNOWN_ENVIRONMENTS, (
        f"unexpected environment {data['environment']!r}"
    )


@pytest.mark.asyncio
async def test_health_root(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_v1(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_root_unauthenticated(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
async def test_health_v1_unauthenticated(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/v1/health")
    assert response.status_code == 200
    _assert_health_body(response.json())


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/api/v1/health"])
async def test_health_503_when_database_unreachable(anon_client: AsyncClient, path: str) -> None:
    bad = create_async_engine("postgresql+asyncpg://health:health@127.0.0.1:9/none")
    app.dependency_overrides[get_health_engine] = lambda: bad
    try:
        response = await anon_client.get(path)
    finally:
        app.dependency_overrides.pop(get_health_engine, None)
        await bad.dispose()
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["database"] == "unavailable"
    for leaked in ("127.0.0.1", "health:health", "Connect", "Error"):
        assert leaked not in response.text


@pytest.mark.asyncio
async def test_database_reachable_times_out() -> None:
    start = time.monotonic()
    assert await database_reachable(_HangingEngine(), timeout=0.05) is False  # type: ignore[arg-type]
    assert time.monotonic() - start < 1.0


@pytest.mark.asyncio
async def test_database_reachable_true_on_real_engine() -> None:
    assert await database_reachable(health_engine, timeout=2.0) is True


@pytest.mark.asyncio
async def test_concurrent_health_checks_share_one_query() -> None:
    fake = _FakeEngine(delay=0.05)
    results = await asyncio.gather(*(cached_database_reachable(fake) for _ in range(20)))  # type: ignore[arg-type]
    assert all(results)
    assert fake.connects == 1


@pytest.mark.asyncio
async def test_health_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "HEALTH_CACHE_SECONDS", 0.0)
    fake = _FakeEngine()
    assert await cached_database_reachable(fake) is True  # type: ignore[arg-type]
    assert await cached_database_reachable(fake) is True  # type: ignore[arg-type]
    assert fake.connects == 2


@pytest.mark.asyncio
async def test_slow_health_check_serves_queued_callers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "HEALTH_CACHE_SECONDS", 0.1)
    fake = _FakeEngine(delay=0.3)
    results = await asyncio.gather(*(cached_database_reachable(fake) for _ in range(20)))  # type: ignore[arg-type]
    assert all(results)
    assert fake.connects == 1
