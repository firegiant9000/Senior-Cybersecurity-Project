"""Unit tests for assessment-intake tier evaluation and preview route.

Phase B2 of the Month 2 plan rebalanced the tier ladder so that BASIC
unlocks on `name + any single identity signal` (domain, vendor, or
asset). Demographic fields (industry / state / employee_range) graduate
into ENHANCED. These tests pin that behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.db.user import User
from app.main import app
from app.schemas.assessment_intake import AssessmentTier
from app.services.assessment_intake import (
    IntakeSnapshot,
    evaluate_intake_preview,
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


def test_basic_tier_unlocks_with_name_plus_primary_domain():
    """Phase B2 wedge: name + primary_domain alone should reach Basic."""
    snap = IntakeSnapshot(name="Acme Co", primary_domain="acme.com")
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.BASIC
    assert result.next_tier == AssessmentTier.ENHANCED


def test_basic_tier_unlocks_with_name_plus_csv_assets():
    """A CSV-only org (no demographics, no domain) still reaches Basic."""
    snap = IntakeSnapshot(name="Acme Co", asset_count=12)
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.BASIC


def test_basic_tier_unlocks_with_name_plus_vendor_row():
    snap = IntakeSnapshot(name="Acme Co", vendor_count=1)
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.BASIC


def test_name_alone_does_not_unlock_basic():
    """Without ANY identity signal, BASIC stays locked even with all demographics."""
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
    )
    result = evaluate_intake_snapshot(snap)
    assert result.current_tier == AssessmentTier.INCOMPLETE
    assert "identity_signal" in result.fields_to_advance


def test_enhanced_requires_demographics_plus_controls():
    snap = IntakeSnapshot(
        name="Acme Co",
        primary_domain="acme.com",
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
        primary_domain="acme.com",
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


def test_unsure_only_controls_count_as_started():
    # 10 controls answered "unsure" → security_controls met (started), depth met
    snap = IntakeSnapshot(
        name="Acme",
        primary_domain="acme.com",
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


# ── evaluate_intake_preview merge behavior ───────────────────────────


@pytest.mark.asyncio
async def test_evaluate_preview_merges_persisted_counts():
    """Persisted vendor/domain/upload counts feed the preview when org exists."""
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        security_controls={"firewall": "yes"},
        # Snapshot starts at zero — the persisted counts should override.
        vendor_count=0,
        domain_count=0,
    )
    org_mock = MagicMock()
    org_mock.id = 7
    session_mock = MagicMock()

    with patch(
        "app.services.assessment_intake._fetch_counts",
        new=AsyncMock(return_value=(2, 3, 0)),
    ), patch(
        "app.services.assessment_intake._fetch_asset_count",
        new=AsyncMock(return_value=0),
    ):
        result = await evaluate_intake_preview(snap, org_mock, session_mock)

    # vendors=2, domains=3, demographics filled, controls started → enhanced
    assert result.current_tier == AssessmentTier.ENHANCED


@pytest.mark.asyncio
async def test_evaluate_preview_optimistic_bumps_win_against_zero_persisted():
    """A typed primary_vendor (snapshot.vendor_count=1) survives a persisted 0."""
    snap = IntakeSnapshot(
        name="Acme Co",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
        security_controls={"firewall": "yes"},
        vendor_count=1,
        domain_count=1,
    )
    org_mock = MagicMock()
    org_mock.id = 7
    session_mock = MagicMock()

    with patch(
        "app.services.assessment_intake._fetch_counts",
        new=AsyncMock(return_value=(0, 0, 0)),
    ), patch(
        "app.services.assessment_intake._fetch_asset_count",
        new=AsyncMock(return_value=0),
    ):
        result = await evaluate_intake_preview(snap, org_mock, session_mock)

    # Snapshot bumps win via max() — demographics + controls → enhanced.
    assert result.current_tier == AssessmentTier.ENHANCED


@pytest.mark.asyncio
async def test_evaluate_preview_without_org_skips_db_lookup():
    """When current_org is None we never touch _fetch_counts."""
    snap = IntakeSnapshot(
        name="Acme Co",
        primary_domain="acme.com",
        industry_label="Technology",
        primary_state="CA",
        employee_range="11-50",
    )
    fetch_mock = AsyncMock(return_value=(99, 99, 99))
    asset_mock = AsyncMock(return_value=99)
    with patch(
        "app.services.assessment_intake._fetch_counts", new=fetch_mock
    ), patch(
        "app.services.assessment_intake._fetch_asset_count", new=asset_mock
    ):
        result = await evaluate_intake_preview(snap, None, MagicMock())

    fetch_mock.assert_not_called()
    asset_mock.assert_not_called()
    # name + primary_domain → BASIC under the new ladder.
    assert result.current_tier == AssessmentTier.BASIC


# ── Route tests ──────────────────────────────────────────────────────


def _fake_user(*, org_id: int | None = None) -> User:
    user = User(
        id=1,
        firebase_uid="test-firebase-uid-global",
        email="testuser@example.com",
        role="viewer",
        auth_provider="password",
        org_id=org_id,
        created_at=datetime.now(UTC),
    )
    user.is_active = True
    return user


@pytest.mark.asyncio
async def test_intake_preview_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.post(
        "/api/v1/organizations/mine/intake-preview",
        json={"name": "Acme"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_intake_preview_works_without_org(client: AsyncClient):
    """First-time onboarding: name + domain alone reaches BASIC."""
    fake_user = _fake_user(org_id=None)

    async def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.post(
            "/api/v1/organizations/mine/intake-preview",
            json={
                "name": "Acme Co",
                "primary_domain": "acme.com",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current_tier"] == "basic"


@pytest.mark.asyncio
async def test_intake_preview_optimistic_vendor_domain(client: AsyncClient):
    """Typed primary_vendor / primary_domain count as +1 even before sync."""
    fake_user = _fake_user(org_id=None)

    async def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
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

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current_tier"] == "enhanced"
