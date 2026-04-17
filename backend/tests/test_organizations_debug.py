"""Integration tests for GET /api/v1/organizations/mine/debug."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.schemas.assessment_debug import (
    DebugAssessmentResponse,
    FindingsReadinessBlock,
    RawOrgProfile,
)
from app.schemas.assessment_intake import AssessmentIntakeResponse, AssessmentTier
from app.schemas.assessment_validation import AssessmentValidationResponse


def _mock_debug_response(org_id: int = 1) -> DebugAssessmentResponse:
    return DebugAssessmentResponse(
        generated_at=datetime.now(tz=UTC),
        org_id=org_id,
        raw_profile=RawOrgProfile(
            id=org_id,
            name="Acme",
            industry_label="Technology",
            ic3_sector="Information",
            primary_state="CA",
            employee_range="11-50",
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        ),
        intake=AssessmentIntakeResponse(
            current_tier=AssessmentTier.ENHANCED,
            tiers=[],
            next_tier=None,
            next_tier_progress=100.0,
            fields_to_advance=[],
        ),
        validation=AssessmentValidationResponse(
            issues=[], score=100.0, passed=True, issue_counts={}
        ),
        findings_readiness=FindingsReadinessBlock(
            ready=True,
            current_tier="enhanced",
        ),
    )


@pytest.mark.asyncio
async def test_debug_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/organizations/mine/debug")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_debug_member_gets_403(client: AsyncClient):
    from fastapi import HTTPException

    from app.core.dependencies import require_org_role
    from app.main import app

    async def _member_denied():
        raise HTTPException(status_code=403, detail="Insufficient org role")

    app.dependency_overrides[require_org_role("admin")] = _member_denied
    try:
        resp = await client.get("/api/v1/organizations/mine/debug")
    finally:
        app.dependency_overrides.pop(require_org_role("admin"), None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_debug_admin_gets_200(client: AsyncClient):
    from app.core.dependencies import get_current_org, require_org_role
    from app.db.organization import Organization
    from app.main import app

    org_mock = MagicMock(spec=Organization)
    org_mock.id = 1

    async def _mock_org():
        return org_mock

    async def _mock_admin():
        return MagicMock()

    app.dependency_overrides[get_current_org] = _mock_org
    app.dependency_overrides[require_org_role("admin")] = _mock_admin
    try:
        with patch(
            "app.api.routes.v1.organizations.build_assessment_debug_snapshot",
            new=AsyncMock(return_value=_mock_debug_response()),
        ):
            resp = await client.get("/api/v1/organizations/mine/debug")
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(require_org_role("admin"), None)

    assert resp.status_code == 200
    body = resp.json()
    assert "org_id" in body
    assert "intake" in body
    assert "validation" in body
    assert "findings_readiness" in body
    assert "raw_profile" in body


@pytest.mark.asyncio
async def test_debug_returns_not_ready_for_basic_tier(client: AsyncClient):
    from app.core.dependencies import get_current_org, require_org_role
    from app.db.organization import Organization
    from app.main import app

    org_mock = MagicMock(spec=Organization)
    org_mock.id = 1

    not_ready_response = _mock_debug_response()
    not_ready_response.findings_readiness = FindingsReadinessBlock(
        ready=False,
        current_tier="basic",
        blocking_reason="Needs Enhanced tier",
    )

    async def _mock_org():
        return org_mock

    async def _mock_admin():
        return MagicMock()

    app.dependency_overrides[get_current_org] = _mock_org
    app.dependency_overrides[require_org_role("admin")] = _mock_admin
    try:
        with patch(
            "app.api.routes.v1.organizations.build_assessment_debug_snapshot",
            new=AsyncMock(return_value=not_ready_response),
        ):
            resp = await client.get("/api/v1/organizations/mine/debug")
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(require_org_role("admin"), None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["findings_readiness"]["ready"] is False
    assert body["findings_readiness"]["blocking_reason"] is not None
