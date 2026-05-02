"""Unit tests for assessment-intake tier evaluation and preview route."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.schemas.assessment_intake import AssessmentTier
from app.services.assessment_intake import (
    IntakeSnapshot,
    evaluate_intake_snapshot,
)

# ── Pure evaluator tests ─────────────────────────────────────────────


def test_empty_snapshot_is_incomplete():
    snap = IntakeSnapshot()
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.INCOMPLETE
    assert result.next_tier == AssessmentTier.BASIC
    assert result.next_tier_progress == 0.0
    assert "name" in result.fields_to_advance


def test_basic_tier_when_all_basic_fields_set():
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.BASIC
    assert result.next_tier == AssessmentTier.ENHANCED


def test_enhanced_requires_vendor_domain_and_controls():
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        vendor_count=1,
        domain_count=1,
        security_controls={"firewall": "yes"},
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.ENHANCED


def test_comprehensive_requires_full_profile():
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        revenue_range="$1M-$10M",
        compliance_frameworks=["SOC 2"],
        data_types=["PII"],
        vendor_count=1,
        domain_count=1,
        upload_count=1,
        security_controls={f"c{i}": "yes" for i in range(8)},
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.COMPREHENSIVE
    assert result.next_tier is None


def test_progress_percent_reflects_partial_next_tier_completion():
    # Basic met, only 1 of 3 enhanced reqs met → 33% toward Enhanced.
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        vendor_count=1,
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.BASIC
    assert result.next_tier == AssessmentTier.ENHANCED
    assert result.next_tier_progress == pytest.approx(33.3, abs=0.1)


def test_unsure_only_controls_count_toward_started_but_not_depth():
    # 10 controls answered "unsure" → security_controls met (started), depth met
    snap = IntakeSnapshot(
        name="Acme",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        vendor_count=1,
        domain_count=1,
        security_controls={f"c{i}": "unsure" for i in range(10)},
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.ENHANCED
    # comprehensive still requires revenue/compliance/data_types/uploads
    assert result.next_tier == AssessmentTier.COMPREHENSIVE


# ── Route tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_preview_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.post(
        "/api/v1/organizations/mine/intake-preview",
        json={"name": "Acme"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_intake_preview_works_without_org(client: AsyncClient):
    """First-time onboarding: user has no org yet, preview still computes."""
    from app.api.routes.v1.auth import get_current_user
    from app.main import app

    user_mock = MagicMock()
    user_mock.org_id = None
    user_mock.role = "user"

    async def _mock_user():
        return user_mock

    app.dependency_overrides[get_current_user] = _mock_user
    try:
        resp = await client.post(
            "/api/v1/organizations/mine/intake-preview",
            json={
                "name": "Acme Co",
                "industry_label": "Technology",
                "primary_state": "CA",
                "employee_range": "11-50",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_tier"] == "basic"


@pytest.mark.asyncio
async def test_intake_preview_optimistic_vendor_domain(client: AsyncClient):
    """Typed primary_vendor / primary_domain count as +1 even before sync."""
    from app.api.routes.v1.auth import get_current_user
    from app.main import app

    user_mock = MagicMock()
    user_mock.org_id = None
    user_mock.role = "user"

    async def _mock_user():
        return user_mock

    app.dependency_overrides[get_current_user] = _mock_user
    try:
        resp = await client.post(
            "/api/v1/organizations/mine/intake-preview",
            json={
                "name": "Acme Co",
                "industry_label": "Technology",
                "primary_state": "CA",
                "employee_range": "11-50",
                "primary_vendor": "AWS",
                "primary_domain": "acme.com",
                "security_controls": {"firewall": "yes"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_tier"] == "enhanced"


@pytest.mark.asyncio
async def test_intake_preview_uses_persisted_counts(client: AsyncClient):
    """When the user has an org, persisted vendor/domain counts feed the preview."""
    from app.api.routes.v1.auth import get_current_user
    from app.main import app

    user_mock = MagicMock()
    user_mock.org_id = 7
    user_mock.role = "user"

    async def _mock_user():
        return user_mock

    app.dependency_overrides[get_current_user] = _mock_user

    org_mock = MagicMock()
    org_mock.id = 7
    scalar = MagicMock()
    scalar.scalar_one_or_none = MagicMock(return_value=org_mock)

    session_execute = AsyncMock(return_value=scalar)

    try:
        with (
            patch(
                "app.api.routes.v1.organizations.AsyncSession.execute",
                new=session_execute,
            ),
            patch(
                "app.services.assessment_intake._fetch_counts",
                new=AsyncMock(return_value=(2, 3, 0)),
            ),
        ):
            resp = await client.post(
                "/api/v1/organizations/mine/intake-preview",
                json={
                    "name": "Acme Co",
                    "industry_label": "Technology",
                    "primary_state": "CA",
                    "employee_range": "11-50",
                    "security_controls": {"firewall": "yes"},
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    # vendors=2, domains=3, controls started → enhanced reachable
    assert body["current_tier"] == "enhanced"
