"""Tests for AI Summary Generation — repository and service persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository


# ---------------------------------------------------------------------------
# Repository unit tests (in-memory mocks, no real DB)
# ---------------------------------------------------------------------------


def _make_session():
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_row(**kwargs):
    row = MagicMock()
    defaults = {
        "id": 1,
        "org_id": 10,
        "generated_at": MagicMock(isoformat=lambda: "2026-04-17T00:00:00+00:00"),
        "model_name": "gemini-1.5-flash",
        "source": "gemini",
        "status": "success",
        "error_message": None,
        "prompt_inputs": {},
        "rendered_prompt": "prompt",
        "output_text": "summary",
        "output_meta": None,
        "findings_snapshot_id": None,
        "triggered_by_user_id": None,
        "latency_ms": 500,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


@pytest.mark.asyncio
async def test_repository_create():
    session = _make_session()
    row = _make_row()
    session.refresh = AsyncMock(side_effect=lambda r: setattr(r, "id", 1))

    with patch(
        "app.repositories.ai_summary_generation.AISummaryGeneration",
        return_value=row,
    ):
        repo = SqlAISummaryGenerationRepository(session)
        result = await repo.create(
            org_id=10,
            model_name="gemini-1.5-flash",
            source="gemini",
            status="success",
            error_message=None,
            prompt_inputs={},
            rendered_prompt="prompt",
            output_text="summary",
            findings_snapshot_id=None,
            triggered_by_user_id=None,
            latency_ms=500,
        )

    session.add.assert_called_once_with(row)
    session.commit.assert_awaited_once()
    assert result is row


@pytest.mark.asyncio
async def test_repository_list_by_org_ordered():
    session = MagicMock()
    rows = [_make_row(id=2), _make_row(id=1)]
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    scalars_mock = MagicMock()
    scalars_mock.scalars.return_value = scalars_result
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        return scalars_mock if call_count == 1 else count_result

    session.execute = mock_execute

    repo = SqlAISummaryGenerationRepository(session)
    items, total = await repo.list_by_org(org_id=10, limit=20, offset=0)

    assert total == 2
    assert len(items) == 2


@pytest.mark.asyncio
async def test_repository_get_returns_none_for_wrong_org():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    repo = SqlAISummaryGenerationRepository(session)
    row = await repo.get(generation_id=99, org_id=10)
    assert row is None


# ---------------------------------------------------------------------------
# Service persistence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_persists_on_gemini_success():
    """AISummaryService.build() calls repo.create on a successful Gemini call."""
    from app.db.organization import Organization
    from app.services.ai_summary import AISummaryService

    org = MagicMock(spec=Organization)
    org.id = 1
    org.name = "Acme"
    org.industry_label = "Tech"
    org.employee_range = "11-50"
    org.primary_state = "CA"

    mock_report = MagicMock()
    mock_report.summary.total = 5
    mock_report.summary.by_severity = {"critical": 1, "high": 2}
    mock_report.assessment_tier = "enhanced"
    mock_report.data_sources_used = []
    mock_report.findings = []

    mock_db = MagicMock()
    # snap_result for findings_snapshot lookup
    snap_scalar = MagicMock()
    snap_scalar.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=snap_scalar)

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
        patch("app.services.ai_summary._get_feedback_meta", new_callable=AsyncMock, return_value=None),
        patch("app.services.ai_summary._call_gemini", new_callable=AsyncMock, return_value="narrative"),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_engine = AsyncMock()
        mock_engine.build.return_value = mock_report
        mock_engine_cls.return_value = mock_engine

        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "gemini-1.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        result = await svc.build(org, triggered_by_user_id=42)

    mock_repo.create.assert_awaited_once()
    call_kwargs = mock_repo.create.call_args.kwargs
    assert call_kwargs["status"] == "success"
    assert call_kwargs["source"] == "gemini"
    assert call_kwargs["triggered_by_user_id"] == 42
    assert result.ai_generated is True


@pytest.mark.asyncio
async def test_service_persists_fallback_on_gemini_error():
    """AISummaryService.build() persists with status=fallback_used when Gemini fails."""
    from app.db.organization import Organization
    from app.services.ai_summary import AISummaryService

    org = MagicMock(spec=Organization)
    org.id = 2
    org.name = "Beta"
    org.industry_label = "Finance"
    org.employee_range = "51-200"
    org.primary_state = "NY"

    mock_report = MagicMock()
    mock_report.summary.total = 3
    mock_report.summary.by_severity = {}
    mock_report.assessment_tier = "good"
    mock_report.data_sources_used = []
    mock_report.findings = []

    mock_db = MagicMock()
    snap_scalar = MagicMock()
    snap_scalar.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=snap_scalar)

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
        patch("app.services.ai_summary._get_feedback_meta", new_callable=AsyncMock, return_value=None),
        patch("app.services.ai_summary._call_gemini", new_callable=AsyncMock, side_effect=Exception("network error")),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_engine = AsyncMock()
        mock_engine.build.return_value = mock_report
        mock_engine_cls.return_value = mock_engine

        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "gemini-1.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        result = await svc.build(org)

    mock_repo.create.assert_awaited_once()
    call_kwargs = mock_repo.create.call_args.kwargs
    assert call_kwargs["status"] == "fallback_used"
    assert call_kwargs["source"] == "fallback"
    assert result.ai_generated is False


@pytest.mark.asyncio
async def test_service_continues_when_persistence_fails():
    """A persistence failure must not propagate — request still returns successfully."""
    from app.db.organization import Organization
    from app.services.ai_summary import AISummaryService

    org = MagicMock(spec=Organization)
    org.id = 3
    org.name = "Gamma"
    org.industry_label = "Health"
    org.employee_range = "1-10"
    org.primary_state = "TX"

    mock_report = MagicMock()
    mock_report.summary.total = 0
    mock_report.summary.by_severity = {}
    mock_report.assessment_tier = "minimal"
    mock_report.data_sources_used = []
    mock_report.findings = []

    mock_db = MagicMock()
    snap_scalar = MagicMock()
    snap_scalar.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=snap_scalar)

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_engine = AsyncMock()
        mock_engine.build.return_value = mock_report
        mock_engine_cls.return_value = mock_engine

        mock_settings.AI_SUMMARY_ENABLED = False
        mock_settings.GEMINI_API_KEY = None
        mock_settings.GEMINI_MODEL = "gemini-1.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo.create.side_effect = Exception("DB down")
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        result = await svc.build(org)

    assert result is not None
    assert result.narrative != ""
