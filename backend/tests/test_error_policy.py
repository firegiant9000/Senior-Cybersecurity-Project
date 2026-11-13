"""Error-message policy: stored errors shown to users hold a class name only (T-PLAT-07)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import app.api.routes.v1.inventory as inventory_module
from tests.test_agent_scan_routes import _clear, _nonce_repo, _override, _payload, _scan_run

RAW = "psycopg ... password=hunter2 host=db.internal"


@pytest.mark.asyncio
async def test_scan_run_status_has_no_raw_exception_text(client: AsyncClient, monkeypatch):
    """A failed agent upload stores only the class name, and the status response
    redacts a legacy row that still holds raw text."""
    row = _scan_run(id=99, status="pending")

    async def _update(scan_run_id, org_id, update):
        for field in ("status", "error_message"):
            value = getattr(update, field, None)
            if value is not None:
                setattr(row, field, value)
        return row

    scan_repo = MagicMock()
    scan_repo.create = AsyncMock(return_value=row)
    scan_repo.update = AsyncMock(side_effect=_update)
    scan_repo.get_by_id = AsyncMock(side_effect=lambda *_: row)
    monkeypatch.setattr(
        inventory_module, "commit_inventory", AsyncMock(side_effect=SQLAlchemyError(RAW))
    )

    _override(scan_repo=scan_repo, nonce_repo=_nonce_repo())
    try:
        upload = await client.post("/api/v1/inventory/scans", json=_payload())
        assert upload.status_code == 500
        assert "password=" not in upload.text

        # What was persisted is the class name, not the exception text.
        assert row.status == "failed"
        assert row.error_message == "SQLAlchemyError"

        status = await client.get("/api/v1/inventory/scans/99")
        assert status.status_code == 200
        assert status.json()["error_message"] == "SQLAlchemyError"
        assert "password=" not in status.text

        # A row written before this fix still holds raw text: the schema redacts it.
        row.error_message = RAW
        legacy = await client.get("/api/v1/inventory/scans/99")
        assert legacy.json()["error_message"] == "error"
        assert "password=" not in legacy.text
    finally:
        _clear()


@pytest.mark.asyncio
async def test_duplicate_scan_reason_stays_readable(client: AsyncClient):
    row = _scan_run(id=99, status="pending")

    async def _update(scan_run_id, org_id, update):
        for field in ("status", "error_message"):
            value = getattr(update, field, None)
            if value is not None:
                setattr(row, field, value)
        return row

    scan_repo = MagicMock()
    scan_repo.create = AsyncMock(return_value=row)
    scan_repo.update = AsyncMock(side_effect=_update)
    scan_repo.get_by_id = AsyncMock(side_effect=lambda *_: row)
    nonce_repo = _nonce_repo()
    nonce_repo.record = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("dup")))

    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        with patch.object(inventory_module, "commit_inventory", AsyncMock(return_value=(1, 3))):
            upload = await client.post("/api/v1/inventory/scans", json=_payload())
        assert upload.status_code == 409
        status = await client.get("/api/v1/inventory/scans/99")
    finally:
        _clear()
    assert status.json()["error_message"] == "DuplicateScanSubmission"


@pytest.mark.asyncio
async def test_csv_import_failure_stores_only_the_class_name(client: AsyncClient):
    update = AsyncMock(return_value=MagicMock())
    pending = MagicMock(id=7)
    with (
        patch("app.api.routes.v1.inventory.check_org_access", new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.scan_runs.SqlScanRunRepository.create",
            AsyncMock(return_value=pending),
        ),
        patch("app.repositories.scan_runs.SqlScanRunRepository.update", update),
        patch(
            "app.api.routes.v1.inventory.commit_inventory",
            new=AsyncMock(side_effect=SQLAlchemyError(RAW)),
        ),
    ):
        resp = await client.post(
            "/api/v1/organizations/1/inventory/uploads/csv/import?confirm=true",
            files={
                "file": ("inv.csv", b"hostname,vendor,product\nweb-1,nginx,nginx\n", "text/csv")
            },
        )
    assert resp.status_code == 500
    assert "password=" not in resp.text
    failed = [c.args[2] for c in update.await_args_list if c.args[2].status == "failed"]
    assert [u.error_message for u in failed] == ["SQLAlchemyError"]


@pytest.mark.asyncio
@pytest.mark.parametrize("exc_type", [FileNotFoundError, NotImplementedError])
@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/vulnerabilities/exploited", "list_exploited"),
        ("/api/v1/vulnerabilities/exploited/severity-summary", "severity_summary"),
        ("/api/v1/vulnerabilities/risk-scored", "list_risk_scored"),
    ],
)
async def test_vulnerabilities_500_detail_is_generic(
    client: AsyncClient, path: str, method: str, exc_type: type[Exception]
):
    from app.main import app
    from app.repositories.exploited_vuln import get_exploited_repo

    repo = MagicMock()
    setattr(
        repo, method, AsyncMock(side_effect=exc_type("/srv/fixtures/kev.json password=hunter2"))
    )
    app.dependency_overrides[get_exploited_repo] = lambda: repo
    try:
        resp = await client.get(path)
    finally:
        app.dependency_overrides.pop(get_exploited_repo, None)
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal error"}
