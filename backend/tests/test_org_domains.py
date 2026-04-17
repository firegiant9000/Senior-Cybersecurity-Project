"""Tests for org domain CRUD endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

fake_domain = MagicMock()
fake_domain.id = 1
fake_domain.org_id = 1
fake_domain.domain_name = "example.com"
fake_domain.is_verified = False
fake_domain.added_by = 1
fake_domain.created_at = datetime(2024, 1, 1, tzinfo=UTC)
fake_domain.updated_at = datetime(2024, 1, 1, tzinfo=UTC)

_ORG_ID = 1
_CHECK_ORG = "app.api.routes.v1.domains.check_org_access"
_REPO_CREATE = "app.repositories.org_domain.SqlOrgDomainRepository.create"
_REPO_LIST = "app.repositories.org_domain.SqlOrgDomainRepository.list_domains"
_REPO_DELETE = "app.repositories.org_domain.SqlOrgDomainRepository.delete"


@pytest.mark.asyncio
async def test_create_domain(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_CREATE, new=AsyncMock(return_value=fake_domain)),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/domains",
            json={"domain_name": "example.com"},
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_domain_conflict(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            _REPO_CREATE,
            new=AsyncMock(side_effect=IntegrityError(None, None, Exception())),
        ),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/domains",
            json={"domain_name": "example.com"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_domain_invalid_name(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/organizations/{_ORG_ID}/domains",
        json={"domain_name": "not-a-domain"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_domains(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_LIST, new=AsyncMock(return_value=([fake_domain], 1))),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/domains")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_delete_domain(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_DELETE, new=AsyncMock(return_value=True)),
    ):
        resp = await client.delete(f"/api/v1/organizations/{_ORG_ID}/domains/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_domain_not_found(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_DELETE, new=AsyncMock(return_value=False)),
    ):
        resp = await client.delete(f"/api/v1/organizations/{_ORG_ID}/domains/999")
    assert resp.status_code == 404
