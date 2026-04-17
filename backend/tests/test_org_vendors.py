"""Tests for org-scoped vendor CRUD and CSV import endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from httpx import AsyncClient

fake_vendor = MagicMock()
fake_vendor.id = 1
fake_vendor.org_id = 1
fake_vendor.vendor_name = "Microsoft"
fake_vendor.product_name = "Windows"
fake_vendor.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
fake_vendor.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
fake_vendor.matched_kev_count = 3

_ORG_ID = 1
_CHECK_ORG = "app.api.routes.v1.vendors._check_org_access"
_REPO_LIST = "app.repositories.org_vendor.SqlOrgVendorRepository.list_vendors"
_REPO_CREATE = "app.repositories.org_vendor.SqlOrgVendorRepository.create"
_REPO_UPDATE = "app.repositories.org_vendor.SqlOrgVendorRepository.update"
_REPO_DELETE = "app.repositories.org_vendor.SqlOrgVendorRepository.delete"
_REPO_BULK = "app.repositories.org_vendor.SqlOrgVendorRepository.bulk_import"


@pytest.mark.asyncio
async def test_list_vendors_empty(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_LIST, new=AsyncMock(return_value=([], 0))),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/vendors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_vendor(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_CREATE, new=AsyncMock(return_value=fake_vendor)),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/vendors",
            json={"vendor_name": "Microsoft", "product_name": "Windows"},
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_vendor_conflict(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            _REPO_CREATE,
            new=AsyncMock(side_effect=IntegrityError(None, None, Exception())),
        ),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/vendors",
            json={"vendor_name": "Microsoft", "product_name": "Windows"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_vendor(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_UPDATE, new=AsyncMock(return_value=fake_vendor)),
    ):
        resp = await client.put(
            f"/api/v1/organizations/{_ORG_ID}/vendors/1",
            json={"vendor_name": "Microsoft", "product_name": "Office"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_vendor_not_found(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_UPDATE, new=AsyncMock(return_value=None)),
    ):
        resp = await client.put(
            f"/api/v1/organizations/{_ORG_ID}/vendors/999",
            json={"vendor_name": "Ghost"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_vendor(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_DELETE, new=AsyncMock(return_value=True)),
    ):
        resp = await client.delete(f"/api/v1/organizations/{_ORG_ID}/vendors/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_vendor_not_found(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_DELETE, new=AsyncMock(return_value=False)),
    ):
        resp = await client.delete(f"/api/v1/organizations/{_ORG_ID}/vendors/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_csv_preview(client: AsyncClient):
    csv_bytes = b"vendor_name,product_name\nMicrosoft,Windows\nAdobe,Reader\n"
    with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/vendors/import/preview",
            files={"file": ("vendors.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["would_import"] == 2


@pytest.mark.asyncio
async def test_csv_import(client: AsyncClient):
    csv_bytes = b"vendor_name,product_name\nMicrosoft,Windows\nAdobe,Reader\n"
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(_REPO_BULK, new=AsyncMock(return_value=(2, 0))),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/vendors/import",
            files={"file": ("vendors.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0
