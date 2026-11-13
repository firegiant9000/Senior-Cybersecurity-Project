"""Per-org quota on forced AI summary refreshes (threat row T-AI-09)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

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
        patch(f"{REPO}.count_gemini_since", new=AsyncMock(return_value=count)),
        patch(f"{REPO}.oldest_gemini_since", new=AsyncMock(return_value=oldest)),
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


def _mock_count_session():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=result)
    return session, result


@pytest.mark.asyncio
async def test_fallback_rows_and_old_rows_not_counted():
    """The count query filters on source == 'gemini' and generated_at >= since."""
    session, _ = _mock_count_session()
    repo = SqlAISummaryGenerationRepository(session)
    since = datetime(2026, 1, 1, tzinfo=UTC)
    assert await repo.count_gemini_since(10, since) == 0
    stmt = session.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))
    assert "ai_summary_generations.org_id = %(org_id_1)s" in sql
    assert "ai_summary_generations.source = %(source_1)s" in sql
    assert "ai_summary_generations.generated_at >= %(generated_at_1)s" in sql
    params = stmt.compile(dialect=postgresql.dialect()).params
    assert params["source_1"] == "gemini"
    assert params["generated_at_1"] == since
    assert params["org_id_1"] == 10
