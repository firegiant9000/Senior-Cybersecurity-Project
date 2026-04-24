"""Integration-style API tests for assessment submission routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.main import app
from app.repositories.assessment_submission import get_assessment_repo


def _mock_submission(*, version: int = 1, is_current: bool = True) -> MagicMock:
    row = MagicMock()
    row.id = "0f5f6a2e-1027-43d3-b012-3d98b8f1f2b8"
    row.organization_id = 1
    row.status = "Draft"
    row.data = {
        "company_profile": {
            "primary_contact_name": "Jane Doe",
            "primary_contact_email": "jane@example.com",
            "employee_count": 45,
            "annual_revenue_usd": 1250000,
            "critical_assets": ["Customer Portal"],
        },
        "security_controls": {
            "mfa_enabled": True,
            "endpoint_protection": True,
            "backup_strategy": "Daily encrypted offsite backups",
            "incident_response_plan": False,
        },
        "risk_assessment": {
            "top_risks": ["Phishing"],
            "compliance_requirements": ["SOC2"],
            "notes": "Need tabletop exercise.",
        },
    }
    row.version = version
    row.is_current = is_current
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    return row


def _valid_payload() -> dict:
    return {
        "organization_id": 1,
        "status": "Draft",
        "data": {
            "company_profile": {
                "primary_contact_name": "Jane Doe",
                "primary_contact_email": "jane@example.com",
                "employee_count": 45,
                "annual_revenue_usd": 1250000,
                "critical_assets": ["Customer Portal"],
            },
            "security_controls": {
                "mfa_enabled": True,
                "endpoint_protection": True,
                "backup_strategy": "Daily encrypted offsite backups",
                "incident_response_plan": False,
            },
            "risk_assessment": {
                "top_risks": ["Phishing"],
                "compliance_requirements": ["SOC2"],
                "notes": "Need tabletop exercise.",
            },
        },
    }


async def _mock_admin_user() -> MagicMock:
    user = MagicMock()
    user.role = "admin"
    user.org_id = 1
    return user


@pytest.mark.asyncio
async def test_create_assessment_returns_201(client: AsyncClient):
    repo = MagicMock()
    repo.create_initial = AsyncMock(return_value=_mock_submission())
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        resp = await client.post("/api/v1/assessments/", json=_valid_payload())
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 201
    body = resp.json()
    assert body["organization_id"] == 1
    assert body["version"] == 1
    assert body["is_current"] is True


@pytest.mark.asyncio
async def test_get_current_assessment_returns_404_when_missing(client: AsyncClient):
    repo = MagicMock()
    repo.get_current_by_org = AsyncMock(return_value=None)
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        resp = await client.get("/api/v1/assessments/1")
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assessment_history_returns_versions(client: AsyncClient):
    repo = MagicMock()
    repo.get_history_by_org = AsyncMock(
        return_value=[
            _mock_submission(version=2, is_current=True),
            _mock_submission(version=1, is_current=False),
        ]
    )
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        resp = await client.get("/api/v1/assessments/1/history")
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["organization_id"] == 1
    assert len(body["submissions"]) == 2


@pytest.mark.asyncio
async def test_update_assessment_creates_new_version(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_mock_submission(version=1, is_current=True))
    repo.create_new_version = AsyncMock(return_value=_mock_submission(version=2, is_current=True))
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        payload = _valid_payload()
        payload.pop("organization_id")
        resp = await client.put(
            "/api/v1/assessments/0f5f6a2e-1027-43d3-b012-3d98b8f1f2b8", json=payload
        )
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_update_assessment_returns_409_for_non_current(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_mock_submission(version=1, is_current=True))
    repo.create_new_version = AsyncMock(
        side_effect=ValueError("Only the current assessment version can be updated")
    )
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        payload = _valid_payload()
        payload.pop("organization_id")
        resp = await client.put("/api/v1/assessments/old-version-id", json=payload)
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_assessment_soft_deletes_version(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_mock_submission(version=2, is_current=True))
    repo.soft_delete = AsyncMock(return_value=_mock_submission(version=2, is_current=False))
    app.dependency_overrides[get_assessment_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        resp = await client.delete("/api/v1/assessments/0f5f6a2e-1027-43d3-b012-3d98b8f1f2b8")
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["is_current"] is False


@pytest.mark.asyncio
async def test_get_current_assessment_cross_tenant_forbidden(client: AsyncClient):
    repo = MagicMock()
    repo.get_current_by_org = AsyncMock(return_value=_mock_submission())
    app.dependency_overrides[get_assessment_repo] = lambda: repo

    async def _org_a_member() -> MagicMock:
        user = MagicMock()
        user.role = "member"
        user.org_id = 1
        return user

    app.dependency_overrides[get_current_user] = _org_a_member
    try:
        resp = await client.get("/api/v1/assessments/2")
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    repo.get_current_by_org.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_assessment_cross_tenant_forbidden(client: AsyncClient):
    repo = MagicMock()
    existing = _mock_submission(version=1, is_current=True)
    existing.organization_id = 2
    repo.get_by_id = AsyncMock(return_value=existing)
    repo.create_new_version = AsyncMock(return_value=_mock_submission(version=2, is_current=True))
    app.dependency_overrides[get_assessment_repo] = lambda: repo

    async def _org_a_member() -> MagicMock:
        user = MagicMock()
        user.role = "member"
        user.org_id = 1
        return user

    app.dependency_overrides[get_current_user] = _org_a_member
    try:
        payload = _valid_payload()
        payload.pop("organization_id")
        resp = await client.put("/api/v1/assessments/org-b-assessment", json=payload)
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    repo.create_new_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_assessment_cross_tenant_forbidden(client: AsyncClient):
    repo = MagicMock()
    repo.create_initial = AsyncMock(return_value=_mock_submission())
    app.dependency_overrides[get_assessment_repo] = lambda: repo

    async def _org_a_member() -> MagicMock:
        user = MagicMock()
        user.role = "member"
        user.org_id = 1
        return user

    app.dependency_overrides[get_current_user] = _org_a_member
    try:
        payload = _valid_payload()
        payload["organization_id"] = 2
        resp = await client.post("/api/v1/assessments/", json=payload)
    finally:
        app.dependency_overrides.pop(get_assessment_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    repo.create_initial.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_assessment_missing_required_nested_field_returns_422(client: AsyncClient):
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        payload = _valid_payload()
        del payload["data"]["security_controls"]["backup_strategy"]
        resp = await client.post("/api/v1/assessments/", json=payload)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_assessment_invalid_boundary_returns_422(client: AsyncClient):
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        payload = _valid_payload()
        payload["data"]["company_profile"]["employee_count"] = 0
        resp = await client.post("/api/v1/assessments/", json=payload)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_assessment_extra_field_returns_422(client: AsyncClient):
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        payload = _valid_payload()
        payload["data"]["company_profile"]["unexpected"] = "not allowed"
        resp = await client.post("/api/v1/assessments/", json=payload)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422
