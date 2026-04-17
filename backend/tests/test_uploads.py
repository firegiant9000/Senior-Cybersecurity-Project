"""Tests for org upload endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

fake_upload = MagicMock()
fake_upload.id = 1
fake_upload.org_id = 1
fake_upload.uploaded_by = 1
fake_upload.original_filename = "test.csv"
fake_upload.stored_filename = "stored_abc.csv"
fake_upload.file_size_bytes = 1024
fake_upload.content_type = "text/csv"
fake_upload.upload_purpose = "test"
fake_upload.created_at = datetime(2024, 1, 1, tzinfo=UTC)

_ORG_ID = 1


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient):
    with (
        patch(
            "app.api.routes.v1.uploads.check_org_access",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.api.routes.v1.uploads.save_upload",
            new=AsyncMock(return_value=("test.csv", "stored_abc.csv", 1024)),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.create",
            new=AsyncMock(return_value=fake_upload),
        ),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/uploads",
            files={"file": ("test.csv", b"col1\nval1\n", "text/csv")},
        )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_uploads(client: AsyncClient):
    with (
        patch(
            "app.api.routes.v1.uploads.check_org_access",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.list_uploads",
            new=AsyncMock(return_value=([fake_upload], 1)),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/uploads")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_upload(client: AsyncClient):
    with (
        patch(
            "app.api.routes.v1.uploads.check_org_access",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.get_by_id",
            new=AsyncMock(return_value=fake_upload),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.delete",
            new=AsyncMock(return_value=fake_upload),
        ),
        patch(
            "app.api.routes.v1.uploads.delete_upload_file",
            new=MagicMock(),
        ),
    ):
        resp = await client.delete(f"/api/v1/organizations/{_ORG_ID}/uploads/1")
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_download_upload_not_found(client: AsyncClient):
    with (
        patch(
            "app.api.routes.v1.uploads.check_org_access",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/uploads/999/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_upload_happy_path(client: AsyncClient, tmp_path):
    stored = tmp_path / "stored_abc.csv"
    stored.write_bytes(b"col1\nval1\n")
    stored_path = str(stored)

    with (
        patch(
            "app.api.routes.v1.uploads.check_org_access",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.get_by_id",
            new=AsyncMock(return_value=fake_upload),
        ),
        patch("app.api.routes.v1.uploads.os.path.exists", new=MagicMock(return_value=True)),
        patch(
            "app.api.routes.v1.uploads.get_upload_path",
            new=MagicMock(return_value=stored_path),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/uploads/1/download")
    assert resp.status_code == 200
