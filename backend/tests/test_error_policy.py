"""Error-message policy: stored errors shown to users hold a class name only (T-PLAT-07)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

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
