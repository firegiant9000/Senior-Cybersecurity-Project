"""Per-org quota on forced AI summary refreshes (threat row T-AI-09)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.config import settings

URL = "/api/v1/organizations/mine/ai-summary"
REPO = "app.repositories.ai_summary_generation.SqlAISummaryGenerationRepository"
SERVICE = "app.api.routes.v1.organizations.AISummaryService"
WINDOW = timedelta(hours=settings.AI_FORCE_REFRESH_WINDOW_HOURS)

_SUMMARY = {
    "narrative": "ok",
    "ai_generated": True,
    "model_used": "gemini-test",
    "findings_count": 0,
    "risk_score": 0.0,
    "risk_label": "low",
    "generated_at": "2026-04-17T00:00:00+00:00",
    "cached": False,
    "disclaimer": "d",
}


@pytest.fixture
def overrides():
    from app.api.routes.v1.auth import get_current_user
    from app.core.dependencies import get_current_org
    from app.db.engine import get_session
    from app.db.organization import Organization
    from app.main import app

    org = MagicMock(spec=Organization)
    org.id = 10

    async def _org():
        return org

    async def _user():
        return MagicMock(id=1, role="admin", org_id=10)

    async def _session():
        return MagicMock()

    app.dependency_overrides[get_current_org] = _org
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_session] = _session
    yield
    for dep in (get_current_org, get_current_user, get_session):
        app.dependency_overrides.pop(dep, None)


def _service_mock():
    service = MagicMock()
    service.invalidate = MagicMock()
    service.build = AsyncMock(return_value=_SUMMARY)
    return service


def _patches(service, count, oldest=None):
    intake = MagicMock(current_tier="enhanced")
    return (
        patch(
            "app.api.routes.v1.organizations.evaluate_intake", new=AsyncMock(return_value=intake)
        ),
        patch(SERVICE, return_value=service),
        patch(f"{REPO}.count_forced_since", new=AsyncMock(return_value=count)),
        patch(f"{REPO}.oldest_forced_since", new=AsyncMock(return_value=oldest)),
    )


async def _get(client, service, count, oldest=None, *, force):
    p1, p2, p3, p4 = _patches(service, count, oldest)
    with p1, p2, p3 as count_mock, p4:
        resp = await client.get(URL, params={"force_refresh": "true"} if force else None)
    return resp, count_mock


@pytest.mark.asyncio
async def test_force_refresh_allowed_under_limit(client, overrides):
    service = _service_mock()
    resp, count_mock = await _get(
        client, service, settings.AI_FORCE_REFRESH_ORG_LIMIT - 1, force=True
    )
    assert resp.status_code == 200
    service.invalidate.assert_called_once_with(10)
    service.build.assert_awaited_once()
    assert service.build.await_args.kwargs["forced"] is True
    # The count looks back one full window from now (UTC).
    since = count_mock.await_args.args[1]
    assert since.tzinfo is not None
    assert abs((datetime.now(UTC) - WINDOW) - since) < timedelta(seconds=30)


@pytest.mark.asyncio
async def test_force_refresh_rejected_at_limit_with_retry_after(client, overrides):
    service = _service_mock()
    oldest = datetime.now(UTC) - WINDOW + timedelta(minutes=90)
    resp, _ = await _get(client, service, settings.AI_FORCE_REFRESH_ORG_LIMIT, oldest, force=True)
    assert resp.status_code == 429
    assert resp.json()["detail"] == "AI summary refresh limit reached for this organization"
    retry_after = int(resp.headers["Retry-After"])
    assert 0 < retry_after <= 90 * 60
    assert retry_after >= 90 * 60 - 5
    service.invalidate.assert_not_called()
    service.build.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_after_is_at_least_one_second(client, overrides):
    service = _service_mock()
    oldest = datetime.now(UTC) - WINDOW - timedelta(seconds=5)  # already leaving
    resp, _ = await _get(client, service, settings.AI_FORCE_REFRESH_ORG_LIMIT, oldest, force=True)
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "1"


@pytest.mark.asyncio
async def test_plain_request_unaffected_at_limit(client, overrides):
    service = _service_mock()
    resp, count_mock = await _get(
        client, service, settings.AI_FORCE_REFRESH_ORG_LIMIT + 5, force=False
    )
    assert resp.status_code == 200
    count_mock.assert_not_awaited()
    service.invalidate.assert_not_called()
    service.build.assert_awaited_once()
    assert service.build.await_args.kwargs["forced"] is False


# ---------------------------------------------------------------------------
# Service: the forced marker is written on every outcome path
# ---------------------------------------------------------------------------


async def _run_build(*, forced, gemini_ok=True, gemini_enabled=True):
    from app.db.organization import Organization
    from app.services.ai_summary import AISummaryService, _cache
    from tests.test_ai_summary_generation import _VALID_JSON

    _cache.clear()
    org = MagicMock(spec=Organization)
    org.id = 1
    org.name = "Acme"
    org.industry_label = "Tech"
    org.employee_range = "11-50"
    org.primary_state = "CA"
    report = MagicMock()
    report.summary.total = 0
    report.summary.by_severity = {}
    report.assessment_tier = "enhanced"
    report.data_sources_used = []
    report.findings = []
    db = MagicMock()
    snap = MagicMock()
    snap.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=snap)
    gemini = (
        AsyncMock(return_value=_VALID_JSON) if gemini_ok else AsyncMock(side_effect=RuntimeError())
    )
    with (
        patch("app.services.ai_summary.FindingsEngine") as engine_cls,
        patch("app.services.ai_summary._get_feedback_meta", new=AsyncMock(return_value=None)),
        patch("app.services.ai_summary._call_gemini", new=gemini),
        patch("app.services.ai_summary.settings") as s,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as repo_cls,
    ):
        engine_cls.return_value = AsyncMock(build=AsyncMock(return_value=report))
        s.AI_SUMMARY_ENABLED = gemini_enabled
        s.GEMINI_API_KEY = "key"
        s.GEMINI_MODEL = "gemini-test"
        s.AI_SUMMARY_CACHE_TTL = 3600
        repo = AsyncMock()
        repo.get_last_successful_gemini.return_value = None
        repo_cls.return_value = repo
        await AISummaryService(db).build(org, forced=forced)
    _cache.clear()
    return repo.create.call_args.kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("gemini_ok", "gemini_enabled"), [(True, True), (False, True), (True, False)]
)
async def test_forced_build_writes_marker_on_every_outcome(gemini_ok, gemini_enabled):
    kwargs = await _run_build(forced=True, gemini_ok=gemini_ok, gemini_enabled=gemini_enabled)
    assert kwargs["output_meta"] == {"forced": True}


@pytest.mark.asyncio
async def test_plain_build_writes_no_marker():
    kwargs = await _run_build(forced=False)
    assert kwargs["output_meta"] is None


# ---------------------------------------------------------------------------
# Repository against real Postgres
# ---------------------------------------------------------------------------


def _row(org_id, generated_at, *, forced, source="gemini"):
    from app.db.ai_summary_generation import AISummaryGeneration

    return AISummaryGeneration(
        org_id=org_id,
        generated_at=generated_at,
        model_name="m",
        source=source,
        status="success",
        prompt_inputs={},
        output_meta={"forced": True} if forced else None,
    )


@pytest.fixture
async def _two_orgs():
    from app.db.engine import AsyncSessionLocal
    from app.db.organization import Organization

    async with AsyncSessionLocal() as session:
        a = Organization(name=f"QuotaOrgA-{uuid4().hex[:8]}")
        b = Organization(name=f"QuotaOrgB-{uuid4().hex[:8]}")
        c = Organization(name=f"QuotaOrgC-{uuid4().hex[:8]}")
        session.add_all([a, b, c])
        await session.flush()
        ids = [a.id, b.id, c.id]
        await session.commit()
        try:
            yield session, *(SimpleNamespace(id=i) for i in ids)
        finally:
            await session.rollback()
            # ai_summary_generations rows go with the org (ON DELETE CASCADE)
            await session.execute(delete(Organization).where(Organization.id.in_(ids)))
            await session.commit()


@pytest.mark.asyncio
async def test_count_and_oldest_forced_since_real_db(_two_orgs):
    from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

    session, a, b, c = _two_orgs
    since = datetime.now(UTC).replace(microsecond=0) - WINDOW
    inside = since + timedelta(hours=3)
    session.add_all(
        [
            _row(a.id, inside, forced=True),
            _row(a.id, since, forced=True),  # exactly at since: counted (>=)
            _row(a.id, since - timedelta(seconds=1), forced=True),  # outside
            _row(a.id, inside, forced=False),  # plain build
            _row(a.id, inside, forced=True, source="fallback"),
            _row(a.id, inside, forced=True, source="gemini_cached"),
            _row(b.id, inside, forced=True),
        ]
    )
    await session.commit()
    repo = SqlAISummaryGenerationRepository(session)
    assert await repo.count_forced_since(a.id, since) == 4
    assert await repo.count_forced_since(b.id, since) == 1
    assert await repo.oldest_forced_since(a.id, since) == since
    assert await repo.oldest_forced_since(c.id, since) is None
    assert await repo.count_forced_since(c.id, since) == 0


@pytest.mark.asyncio
async def test_plain_builds_not_counted(_two_orgs):
    from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

    session, a, _b, _c = _two_orgs
    since = datetime.now(UTC) - WINDOW
    session.add_all(
        [_row(a.id, datetime.now(UTC), forced=False) for _ in range(12)]
        + [_row(a.id, datetime.now(UTC), forced=False, source="fallback")]
    )
    await session.commit()
    assert await SqlAISummaryGenerationRepository(session).count_forced_since(a.id, since) == 0


@pytest.mark.asyncio
async def test_rows_outside_window_not_counted(_two_orgs):
    from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

    session, a, _b, _c = _two_orgs
    since = datetime.now(UTC) - WINDOW
    session.add_all([_row(a.id, since - timedelta(hours=h), forced=True) for h in (1, 5, 48)])
    await session.commit()
    repo = SqlAISummaryGenerationRepository(session)
    assert await repo.count_forced_since(a.id, since) == 0
    assert await repo.oldest_forced_since(a.id, since) is None
