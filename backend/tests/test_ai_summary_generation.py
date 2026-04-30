"""Tests for AI Summary Generation — repository and service persistence."""

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
        patch(
            "app.services.ai_summary._get_feedback_meta", new_callable=AsyncMock, return_value=None
        ),
        patch(
            "app.services.ai_summary._call_gemini", new_callable=AsyncMock, return_value="narrative"
        ),
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
        patch(
            "app.services.ai_summary._get_feedback_meta", new_callable=AsyncMock, return_value=None
        ),
        patch(
            "app.services.ai_summary._call_gemini",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ),
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


# ---------------------------------------------------------------------------
# _parse_structured_response — JSON mode parsing and fallback
# ---------------------------------------------------------------------------

_VALID_JSON = """{
    "narrative": "Overall risk is moderate.",
    "posture_statement": "The org is at moderate risk.",
    "notable_risks": [{"title": "Ransomware exposure", "severity": "high", "context": "IC3 data"}],
    "data_gaps": [{"gap_type": "missing_domains", "impact": "Incomplete domain analysis"}],
    "next_steps": [{"priority": 1, "action": "Patch vendors", "rationale": "KEV match found"}]
}"""

_FENCED_JSON = f"```json\n{_VALID_JSON}\n```"
_FENCED_NO_LANG = f"```\n{_VALID_JSON}\n```"


def test_parse_structured_response_valid_json():
    from app.services.ai_summary import _parse_structured_response

    result = _parse_structured_response(_VALID_JSON)
    assert result is not None
    assert result.narrative == "Overall risk is moderate."
    assert result.posture_statement == "The org is at moderate risk."
    assert len(result.notable_risks) == 1
    assert result.notable_risks[0].title == "Ransomware exposure"
    assert len(result.data_gaps) == 1
    assert len(result.next_steps) == 1
    assert result.next_steps[0].priority == 1


def test_parse_structured_response_strips_markdown_fence_with_lang():
    from app.services.ai_summary import _parse_structured_response

    result = _parse_structured_response(_FENCED_JSON)
    assert result is not None
    assert result.narrative == "Overall risk is moderate."


def test_parse_structured_response_strips_markdown_fence_no_lang():
    from app.services.ai_summary import _parse_structured_response

    result = _parse_structured_response(_FENCED_NO_LANG)
    assert result is not None
    assert result.narrative == "Overall risk is moderate."


def test_parse_structured_response_malformed_json_returns_none():
    from app.services.ai_summary import _parse_structured_response

    result = _parse_structured_response("This is just a plain prose narrative, not JSON.")
    assert result is None


def test_parse_structured_response_missing_required_field_returns_none():
    from app.services.ai_summary import _parse_structured_response

    # narrative field is required — omitting it should fail validation
    incomplete = (
        '{"posture_statement": "ok", "notable_risks": [], "data_gaps": [], "next_steps": []}'
    )
    result = _parse_structured_response(incomplete)
    assert result is None


def test_parse_structured_response_empty_string_returns_none():
    from app.services.ai_summary import _parse_structured_response

    assert _parse_structured_response("") is None
    assert _parse_structured_response("   ") is None


# ---------------------------------------------------------------------------
# Service: output_format set correctly based on parse outcome
# ---------------------------------------------------------------------------


def _base_service_patches(gemini_raw: str, gemini_raises: Exception | None = None):
    """Return the common patch set for AISummaryService.build() tests."""
    from unittest.mock import AsyncMock, MagicMock

    org = MagicMock()
    org.id = 99
    org.name = "TestCo"
    org.industry_label = "Tech & Software"
    org.employee_range = "11-50"
    org.primary_state = "CA"

    mock_report = MagicMock()
    mock_report.summary.total = 2
    mock_report.summary.by_severity = {}
    mock_report.assessment_tier = "enhanced"
    mock_report.data_sources_used = []
    mock_report.findings = []

    mock_db = MagicMock()
    snap = MagicMock()
    snap.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=snap)

    return org, mock_report, mock_db


@pytest.mark.asyncio
async def test_service_output_format_json_on_successful_parse():
    from unittest.mock import AsyncMock, patch

    from app.services.ai_summary import AISummaryService

    org, mock_report, mock_db = _base_service_patches(_VALID_JSON)

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_eng,
        patch("app.services.ai_summary._get_feedback_meta", new=AsyncMock(return_value=None)),
        patch("app.services.ai_summary._call_gemini", new=AsyncMock(return_value=_VALID_JSON)),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_eng.return_value.build = AsyncMock(return_value=mock_report)
        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        result = await svc.build(org)

    kwargs = mock_repo.create.call_args.kwargs
    assert kwargs["output_format"] == "json"
    assert result.posture_statement == "The org is at moderate risk."
    assert result.notable_risks is not None


@pytest.mark.asyncio
async def test_service_invalidate_bypasses_cache_on_next_build():
    """invalidate(org_id) drops the cached response so the next build() rebuilds.

    Mirrors the endpoint's force_refresh=true path: route calls
    service.invalidate(org.id) before service.build(org).
    """
    from unittest.mock import AsyncMock, patch

    from app.services.ai_summary import AISummaryService

    org, mock_report, mock_db = _base_service_patches(_VALID_JSON)

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_eng,
        patch("app.services.ai_summary._get_feedback_meta", new=AsyncMock(return_value=None)),
        patch("app.services.ai_summary._call_gemini", new=AsyncMock(return_value=_VALID_JSON)),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_eng.return_value.build = AsyncMock(return_value=mock_report)
        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        svc.invalidate(org.id)  # ensure clean cache

        first = await svc.build(org)
        assert first.cached is False
        assert mock_repo.create.await_count == 1

        cached = await svc.build(org)
        assert cached.cached is True
        # No new persistence call when serving from cache
        assert mock_repo.create.await_count == 1

        svc.invalidate(org.id)
        fresh = await svc.build(org)
        assert fresh.cached is False
        assert mock_repo.create.await_count == 2


@pytest.mark.asyncio
async def test_service_output_format_prose_when_parse_fails():
    from unittest.mock import AsyncMock, patch

    from app.services.ai_summary import AISummaryService

    org, mock_report, mock_db = _base_service_patches("")

    with (
        patch("app.services.ai_summary.FindingsEngine") as mock_eng,
        patch("app.services.ai_summary._get_feedback_meta", new=AsyncMock(return_value=None)),
        patch(
            "app.services.ai_summary._call_gemini",
            new=AsyncMock(return_value="Not JSON at all, just prose."),
        ),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as mock_repo_cls,
    ):
        mock_eng.return_value.build = AsyncMock(return_value=mock_report)
        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        svc = AISummaryService(mock_db)
        svc.invalidate(org.id)  # clear any cache left by a prior test
        result = await svc.build(org)

    kwargs = mock_repo.create.call_args.kwargs
    assert kwargs["output_format"] == "prose"
    # Structured fields are absent when parse fails
    assert result.notable_risks is None
    assert result.data_gaps is None
    assert result.next_steps is None
