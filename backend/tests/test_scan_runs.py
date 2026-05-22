"""Tests for the Month 2 Phase A scan_run + vendor_alias data model + repos."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.scan_run import ScanRun
from app.db.vendor_alias import VendorAlias
from app.repositories.scan_runs import SqlScanRunRepository
from app.repositories.vendor_aliases import SqlVendorAliasRepository
from app.schemas.scan_run import (
    ScanRunCreate,
    ScanRunListResponse,
    ScanRunRead,
    ScanRunUpdate,
)
from app.schemas.vendor_alias import VendorAliasCreate
from app.services.data_status import list_data_status


def test_scan_run_orm():
    assert ScanRun.__tablename__ == "scan_runs"
    indexed_names = {idx.name for idx in ScanRun.__table__.indexes}
    assert "ix_scan_runs_org_started" in indexed_names


def test_vendor_alias_orm():
    assert VendorAlias.__tablename__ == "vendor_aliases"
    constraint_names = {c.name for c in VendorAlias.__table__.constraints}
    assert "uq_vendor_aliases_alias" in constraint_names


def test_scan_run_create_schema():
    s = ScanRunCreate(source="csv_upload", triggered_by_user_id=1)
    assert s.source == "csv_upload"


def test_scan_run_create_rejects_bad_source():
    with pytest.raises(ValueError):
        ScanRunCreate(source="bogus")  # type: ignore[arg-type]


def test_scan_run_update_partial():
    upd = ScanRunUpdate(status="succeeded", asset_count=5)
    payload = upd.model_dump(exclude_unset=True, exclude_none=True)
    assert payload == {"status": "succeeded", "asset_count": 5}


def test_scan_run_list_response():
    resp = ScanRunListResponse(total=0, page=1, page_size=20, items=[])
    assert resp.items == []


def test_scan_run_read_round_trip():
    fake = MagicMock()
    fake.id = 1
    fake.org_id = 1
    fake.source = "csv_upload"
    fake.status = "succeeded"
    fake.started_at = datetime(2026, 5, 1, tzinfo=UTC)
    fake.finished_at = datetime(2026, 5, 1, tzinfo=UTC)
    fake.asset_count = 3
    fake.software_count = 9
    fake.error_message = None
    fake.scan_metadata = {"rows": 3}
    fake.triggered_by_user_id = 1
    read = ScanRunRead.model_validate(fake)
    assert read.asset_count == 3


@pytest.mark.asyncio
async def test_scan_run_repo_get_by_id_scopes_by_org():
    session = MagicMock()
    captured: dict[str, object] = {}

    async def _execute(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = SqlScanRunRepository(session)
    await repo.get_by_id(7, org_id=42)
    rendered = str(captured["stmt"])
    assert "org_id" in rendered


@pytest.mark.asyncio
async def test_vendor_alias_resolve_falls_back_to_input():
    session = MagicMock()

    async def _execute(_stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = SqlVendorAliasRepository(session)
    canonical = await repo.resolve("Some Unknown Vendor Inc.")
    # Falls back to lowercased + stripped input.
    assert canonical == "some unknown vendor inc."


@pytest.mark.asyncio
async def test_vendor_alias_resolve_returns_canonical():
    session = MagicMock()

    async def _execute(_stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = "microsoft"
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = SqlVendorAliasRepository(session)
    canonical = await repo.resolve("Microsoft Corp")
    assert canonical == "microsoft"


def test_vendor_alias_create_schema():
    a = VendorAliasCreate(canonical_vendor="microsoft", alias="Microsoft Corp")
    assert a.source == "manual"


def test_data_status_registers_phase_a_sources():
    keys = {item.key for item in list_data_status()}
    assert "assets_inventory" in keys
    assert "asset_software" in keys
    assert "scan_runs" in keys
    assert "vendor_aliases" in keys
