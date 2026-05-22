"""Route-level tests for the inventory upload + assets endpoints (Phase C)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

_ORG_ID = 1
_CHECK_ORG = "app.api.routes.v1.inventory.check_org_access"


def _make_scan_run(scan_id: int = 7, **overrides) -> MagicMock:
    run = MagicMock()
    run.id = scan_id
    run.org_id = _ORG_ID
    run.source = "csv_upload"
    run.status = overrides.get("status", "succeeded")
    run.started_at = datetime(2026, 5, 21, tzinfo=UTC)
    run.finished_at = overrides.get("finished_at", datetime(2026, 5, 21, tzinfo=UTC))
    run.asset_count = overrides.get("asset_count", 2)
    run.software_count = overrides.get("software_count", 3)
    run.error_message = None
    run.scan_metadata = overrides.get("metadata", {"kev_matches": 1})
    run.triggered_by_user_id = 1
    return run


@pytest.mark.asyncio
async def test_preview_rejects_missing_required_column(client: AsyncClient):
    csv_bytes = b"bogus\nvalue\n"
    with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/inventory/uploads/csv/preview",
            files={"file": ("inv.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid_rows"] == 0
    assert any("Missing required columns" in e["errors"][0] for e in body["invalid_rows"])


@pytest.mark.asyncio
async def test_preview_counts_assets_and_software(client: AsyncClient):
    csv_bytes = (
        b"hostname,vendor,product,version\n"
        b"web-1,nginx,nginx,1.24.0\n"
        b"web-1,openssl,openssl,3.0.2\n"
        b"db-1,PostgreSQL,postgresql,15.4\n"
    )
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.assets.SqlAssetRepository.get_by_hostname",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/inventory/uploads/csv/preview",
            files={"file": ("inv.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid_rows"] == 3
    assert body["distinct_assets"] == 2
    assert body["distinct_software"] == 3
    assert body["would_create"] == 2
    assert body["would_update"] == 0


@pytest.mark.asyncio
async def test_import_requires_confirm(client: AsyncClient):
    csv_bytes = b"hostname,vendor,product\nweb-1,nginx,nginx\n"
    with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/inventory/uploads/csv/import",
            files={"file": ("inv.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 400
    assert "confirm" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_rejects_empty_csv(client: AsyncClient):
    csv_bytes = b"hostname,vendor,product\n,nginx,nginx\n"
    with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/inventory/uploads/csv/import?confirm=true",
            files={"file": ("inv.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_happy_path(client: AsyncClient):
    csv_bytes = (
        b"hostname,vendor,product,version\n"
        b"web-1,nginx,nginx,1.24.0\n"
        b"db-1,PostgreSQL,postgresql,15.4\n"
    )
    pending_run = _make_scan_run(status="pending", asset_count=0, software_count=0)
    final_run = _make_scan_run(
        status="succeeded",
        asset_count=2,
        software_count=2,
        metadata={"kev_matches": 0},
    )
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.scan_runs.SqlScanRunRepository.create",
            new=AsyncMock(return_value=pending_run),
        ),
        patch(
            "app.repositories.scan_runs.SqlScanRunRepository.update",
            new=AsyncMock(return_value=final_run),
        ),
        patch(
            "app.api.routes.v1.inventory.commit_inventory",
            new=AsyncMock(return_value=(2, 2)),
        ),
        patch(
            "app.api.routes.v1.inventory.count_kev_matches",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "app.api.routes.v1.inventory._audit",
            new=AsyncMock(return_value=None),
        ),
        # Stub session.commit so it doesn't actually hit the DB.
        patch(
            "sqlalchemy.ext.asyncio.AsyncSession.commit",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.post(
            f"/api/v1/organizations/{_ORG_ID}/inventory/uploads/csv/import?confirm=true",
            files={"file": ("inv.csv", csv_bytes, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["asset_count"] == 2
    assert body["software_count"] == 2


@pytest.mark.asyncio
async def test_scan_run_not_found(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.scan_runs.SqlScanRunRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/scan-runs/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_assets_empty(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.assets.SqlAssetRepository.list_assets",
            new=AsyncMock(return_value=([], 0)),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/assets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
