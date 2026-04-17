"""Unit tests for the assessment debug service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.organization import Organization
from app.schemas.assessment_intake import AssessmentIntakeResponse, AssessmentTier
from app.schemas.assessment_validation import AssessmentValidationResponse
from app.schemas.findings import FindingsReport, FindingsSummary
from app.services.assessment_validator import _ValidationResult


def _org(org_id: int = 1) -> Organization:
    org = MagicMock(spec=Organization)
    org.id = org_id
    org.name = "Acme"
    return org


def _intake(tier: str = "enhanced") -> AssessmentIntakeResponse:
    return AssessmentIntakeResponse(
        current_tier=AssessmentTier(tier),
        tiers=[],
        next_tier=None,
        next_tier_progress=100.0,
        fields_to_advance=[],
    )


def _validation() -> AssessmentValidationResponse:
    return AssessmentValidationResponse(issues=[], score=100.0, passed=True, issue_counts={})


def _findings_report(org_id: int = 1) -> FindingsReport:
    return FindingsReport(
        org_id=org_id,
        findings=[],
        summary=FindingsSummary(total=0, by_type={}, by_severity={}),
        generated_at="2024-01-01T00:00:00Z",
        data_sources_used=[],
        assessment_tier="enhanced",
    )


@pytest.mark.asyncio
async def test_debug_snapshot_composition():
    org = _org()
    db = AsyncMock()

    with (
        patch(
            "app.services.assessment_debug.evaluate_intake",
            new=AsyncMock(return_value=_intake("enhanced")),
        ),
        patch(
            "app.services.assessment_debug.run_validation",
            new=AsyncMock(return_value=_ValidationResult()),
        ),
        patch(
            "app.services.assessment_debug.build_response",
            return_value=_validation(),
        ),
        patch(
            "app.services.assessment_debug.FindingsEngine",
        ) as MockEngine,
    ):
        MockEngine.return_value.build = AsyncMock(return_value=_findings_report())

        from app.services.assessment_debug import build_assessment_debug_snapshot

        result = await build_assessment_debug_snapshot(org, db)

    assert result.org_id == org.id
    assert result.findings_readiness.ready is True
    assert result.findings_readiness.report is not None
    MockEngine.return_value.build.assert_awaited_once_with(org, persist=False)


@pytest.mark.asyncio
async def test_debug_snapshot_skips_findings_below_enhanced():
    org = _org()
    db = AsyncMock()

    with (
        patch(
            "app.services.assessment_debug.evaluate_intake",
            new=AsyncMock(return_value=_intake("basic")),
        ),
        patch(
            "app.services.assessment_debug.run_validation",
            new=AsyncMock(return_value=_ValidationResult()),
        ),
        patch(
            "app.services.assessment_debug.build_response",
            return_value=_validation(),
        ),
        patch("app.services.assessment_debug.FindingsEngine") as MockEngine,
    ):
        from app.services.assessment_debug import build_assessment_debug_snapshot

        result = await build_assessment_debug_snapshot(org, db)

    assert result.findings_readiness.ready is False
    assert result.findings_readiness.blocking_reason is not None
    MockEngine.return_value.build.assert_not_called()


@pytest.mark.asyncio
async def test_debug_snapshot_skips_findings_for_incomplete():
    org = _org()
    db = AsyncMock()

    with (
        patch(
            "app.services.assessment_debug.evaluate_intake",
            new=AsyncMock(return_value=_intake("incomplete")),
        ),
        patch(
            "app.services.assessment_debug.run_validation",
            new=AsyncMock(return_value=_ValidationResult()),
        ),
        patch(
            "app.services.assessment_debug.build_response",
            return_value=_validation(),
        ),
        patch("app.services.assessment_debug.FindingsEngine") as MockEngine,
    ):
        from app.services.assessment_debug import build_assessment_debug_snapshot

        result = await build_assessment_debug_snapshot(org, db)

    assert result.findings_readiness.ready is False
    MockEngine.return_value.build.assert_not_called()
