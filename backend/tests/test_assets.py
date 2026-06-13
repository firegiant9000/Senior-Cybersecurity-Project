"""Tests for the Month 2 Phase A asset / asset_software data model + repos."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.asset import Asset
from app.db.asset_software import AssetSoftware
from app.repositories.asset_software import SqlAssetSoftwareRepository
from app.repositories.assets import SqlAssetRepository
from app.schemas.asset import (
    AssetCreate,
    AssetListResponse,
    AssetRead,
    AssetTagsUpdate,
    AssetUpdate,
)
from app.schemas.asset_software import AssetSoftwareCreate, AssetSoftwareRead


def test_asset_orm_table_args():
    assert Asset.__tablename__ == "assets"
    indexed_names = {idx.name for idx in Asset.__table__.indexes}
    assert "ix_assets_org_hostname" in indexed_names
    assert "ix_assets_org_is_active" in indexed_names


def test_asset_software_orm_table_args():
    assert AssetSoftware.__tablename__ == "asset_software"
    indexed_names = {idx.name for idx in AssetSoftware.__table__.indexes}
    assert "ix_asset_software_org_vendor_product" in indexed_names


def test_asset_create_schema_rejects_bad_discovered_via():
    with pytest.raises(ValueError):
        AssetCreate(hostname="h1", discovered_via="bogus")  # type: ignore[arg-type]


def test_asset_create_schema_accepts_minimal():
    a = AssetCreate(hostname="srv-01", discovered_via="csv_upload")
    assert a.hostname == "srv-01"
    assert a.ip_address is None


def test_asset_read_round_trip():
    fake = MagicMock()
    fake.id = 7
    fake.org_id = 3
    fake.hostname = "srv-01"
    fake.ip_address = "10.0.0.1"
    fake.os_name = "Windows 11"
    fake.os_version = "23H2"
    fake.mac_address = None
    fake.discovered_via = "csv_upload"
    fake.asset_criticality = "normal"
    fake.first_seen = datetime(2026, 5, 1, tzinfo=UTC)
    fake.last_seen = datetime(2026, 5, 1, tzinfo=UTC)
    fake.is_active = True
    fake.asset_metadata = {"k": "v"}
    fake.tags = None
    fake.created_by_scan_run_id = None
    fake.created_at = datetime(2026, 5, 1, tzinfo=UTC)
    fake.updated_at = datetime(2026, 5, 1, tzinfo=UTC)
    read = AssetRead.model_validate(fake)
    assert read.hostname == "srv-01"
    assert read.source == "csv_upload"


def test_asset_software_create_requires_vendor_product():
    with pytest.raises(ValueError):
        AssetSoftwareCreate(vendor="", product="Office", source="csv_upload")
    with pytest.raises(ValueError):
        AssetSoftwareCreate(vendor="Microsoft", product="", source="csv_upload")


def test_asset_list_response_shape():
    resp = AssetListResponse(total=0, page=1, page_size=50, items=[])
    assert resp.total == 0
    assert resp.items == []


@pytest.mark.asyncio
async def test_asset_repo_get_by_id_scopes_by_org():
    """get_by_id must include org_id in the WHERE clause to prevent cross-org leakage."""
    session = MagicMock()
    captured: dict[str, object] = {}

    async def _execute(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = SqlAssetRepository(session)
    await repo.get_by_id(42, org_id=99)
    rendered = str(captured["stmt"])
    assert "org_id" in rendered
    assert "assets.id" in rendered


@pytest.mark.asyncio
async def test_asset_software_repo_list_for_asset_filters_by_org():
    session = MagicMock()
    captured: dict[str, object] = {}

    async def _execute(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = SqlAssetSoftwareRepository(session)
    await repo.list_for_asset(asset_id=1, org_id=5)
    rendered = str(captured["stmt"])
    assert "asset_id" in rendered
    assert "org_id" in rendered


def test_asset_update_partial_payload():
    upd = AssetUpdate(is_active=False)
    payload = upd.model_dump(exclude_unset=True, exclude_none=True)
    assert payload == {"is_active": False}


def test_asset_tags_update_schema_caps_count():
    AssetTagsUpdate(tags=["a"] * 32)  # exactly 32 allowed
    with pytest.raises(ValueError):
        AssetTagsUpdate(tags=["a"] * 33)


@pytest.mark.asyncio
async def test_asset_set_tags_normalizes_and_dedupes():
    """Tags are lowercased, whitespace-collapsed, dedup'd, length-capped."""
    asset = MagicMock(spec=Asset)
    asset.tags = None
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=asset))
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    repo = SqlAssetRepository(session)
    out = await repo.set_tags(
        1,
        org_id=1,
        tags=["  Prod  ", "prod", "PCI Zone", "x" * 100, "", "executive-laptop"],
    )
    assert out is asset
    # "Prod" and "prod" dedup; whitespace collapsed; >64-char dropped; empty dropped.
    assert asset.tags == ["prod", "pci zone", "executive-laptop"]


def test_asset_software_read_has_source():
    sw = AssetSoftwareRead(
        id=1,
        asset_id=1,
        org_id=1,
        vendor="Microsoft",
        product="Office",
        version="2024",
        cpe_uri=None,
        source="csv_upload",
        first_seen=datetime(2026, 5, 1, tzinfo=UTC),
        last_seen=datetime(2026, 5, 1, tzinfo=UTC),
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert sw.source == "csv_upload"
