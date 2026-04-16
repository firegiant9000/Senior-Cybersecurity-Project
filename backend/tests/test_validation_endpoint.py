"""Integration tests for GET /api/v1/organizations/mine/validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validation_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.get("/api/v1/organizations/mine/validation")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_validation_no_org(client: AsyncClient):
    """Authenticated user with no org should get 403."""
    from fastapi import HTTPException

    from app.core.dependencies import get_current_org
    from app.main import app

    async def _no_org():
        raise HTTPException(status_code=403, detail="No organization membership")

    app.dependency_overrides[get_current_org] = _no_org
    try:
        resp = await client.get("/api/v1/organizations/mine/validation")
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_validation_returns_structure(client: AsyncClient):
    """Authenticated user with org gets a valid validation response."""
    from app.core.dependencies import get_current_org
    from app.db.organization import Organization
    from app.main import app
    from app.services.assessment_validator import _ValidationResult

    org_mock = MagicMock(spec=Organization)
    org_mock.id = 1

    empty_result = _ValidationResult()

    async def _mock_org():
        return org_mock

    app.dependency_overrides[get_current_org] = _mock_org
    try:
        with patch(
            "app.api.routes.v1.organizations.run_validation",
            new=AsyncMock(return_value=empty_result),
        ):
            resp = await client.get("/api/v1/organizations/mine/validation")
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    assert resp.status_code == 200
    body = resp.json()
    assert "issues" in body
    assert "score" in body
    assert "passed" in body
    assert "issue_counts" in body
    assert set(body["issue_counts"].keys()) == {"error", "warning", "info"}
