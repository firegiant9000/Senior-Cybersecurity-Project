"""Admin read route for the anonymous readiness funnel counters (#296)."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete

from app.api.routes.v1.auth import get_current_user
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal
from app.db.readiness_funnel_count import ReadinessFunnelCount
from app.main import app
from app.repositories.readiness_funnel import SqlReadinessFunnelRepository

URL = "/api/v1/analytics/readiness-funnel"
NOTE = "Directional only: anyone can call the counting route, so these numbers can be inflated."
D1, D2, D3 = date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 12)


async def _wipe() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ReadinessFunnelCount))
        await session.commit()


def _as_role(role: str) -> None:
    async def _user():
        return SimpleNamespace(id=1, email="u@example.com", org_id=1, role=role)

    app.dependency_overrides[get_current_user] = _user


@pytest_asyncio.fixture
async def seeded():
    limiter.reset()
    await _wipe()
    async with AsyncSessionLocal() as session:
        repo = SqlReadinessFunnelRepository(session)
        await repo.increment(D1, "v1", "quiz_started")
        await repo.increment(D2, "v1", "quiz_started")
        await repo.increment(D2, "v1", "quiz_started")
        await repo.increment(D2, "v1", "quiz_completed")
        await repo.increment(D3, "v1", "quiz_started")
        await session.commit()
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        limiter.reset()
        await _wipe()


@pytest.mark.asyncio
async def test_admin_reads_counts_in_range(client: AsyncClient, seeded):
    _as_role("admin")
    resp = await client.get(URL, params={"start": str(D2), "end": str(D3)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["start"] == str(D2)
    assert body["end"] == str(D3)
    assert body["note"] == NOTE
    assert body["counts"] == [
        {"day": str(D2), "version": "v1", "step": "quiz_completed", "count": 1},
        {"day": str(D2), "version": "v1", "step": "quiz_started", "count": 2},
        {"day": str(D3), "version": "v1", "step": "quiz_started", "count": 1},
    ]


@pytest.mark.asyncio
async def test_non_admin_cannot_read_counts(client: AsyncClient, anon_client: AsyncClient, seeded):
    params = {"start": str(D1), "end": str(D3)}
    _as_role("member")
    assert (await client.get(URL, params=params)).status_code == 403
    app.dependency_overrides.pop(get_current_user, None)
    assert (await anon_client.get(URL, params=params)).status_code == 401


@pytest.mark.asyncio
async def test_bad_range_is_422(client: AsyncClient, seeded):
    _as_role("admin")
    start = date(2025, 1, 1)
    resp = await client.get(URL, params={"start": str(D2), "end": str(D1)})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "end must not be before start"

    over = await client.get(URL, params={"start": str(start), "end": str(start + timedelta(367))})
    assert over.status_code == 422
    assert over.json()["detail"] == "range is limited to 366 days"

    edge = await client.get(URL, params={"start": str(start), "end": str(start + timedelta(365))})
    assert edge.status_code == 200

    assert (await client.get(URL, params={"start": str(start)})).status_code == 422
