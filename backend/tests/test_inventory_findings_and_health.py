"""Tests for the Phase F2/F3 endpoints:

- ``GET /organizations/{org_id}/assets/{asset_id}/findings``
- ``GET /organizations/{org_id}/inventory/health``
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

_ORG_ID = 1
_ASSET_ID = 42
_CHECK_ORG = "app.api.routes.v1.inventory.check_org_access"


def _exec_result_scalars(rows: list[object]) -> MagicMock:
    """Mimic ``(await session.execute(...)).scalars().all() == rows``."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    result.scalars.return_value = scalars
    return result


def _exec_result_rows(rows: list[tuple]) -> MagicMock:
    """Mimic ``(await session.execute(...)).all() == rows``."""
    result = MagicMock()
    result.all.return_value = rows
    return result


def _exec_result_scalar_one(value: object) -> MagicMock:
    """Mimic ``(await session.execute(...)).scalar_one() == value``."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _exec_result_first(row: tuple | None) -> MagicMock:
    """Mimic ``(await session.execute(...)).first() == row``."""
    result = MagicMock()
    result.first.return_value = row
    return result


def _make_software(*, sid: int, vendor: str, product: str, version: str | None = None):
    sw = MagicMock()
    sw.id = sid
    sw.org_id = _ORG_ID
    sw.asset_id = _ASSET_ID
    sw.vendor = vendor
    sw.product = product
    sw.version = version
    sw.cpe_uri = None
    sw.source = "csv_upload"
    sw.first_seen = datetime(2026, 5, 1, tzinfo=UTC)
    sw.last_seen = datetime(2026, 5, 1, tzinfo=UTC)
    sw.created_at = datetime(2026, 5, 1, tzinfo=UTC)
    return sw


def _make_asset():
    a = MagicMock()
    a.id = _ASSET_ID
    a.org_id = _ORG_ID
    a.hostname = "srv-01"
    a.ip_address = "10.0.0.1"
    a.os_name = "Ubuntu"
    a.os_version = "22.04"
    a.mac_address = None
    a.discovered_via = "csv_upload"
    a.first_seen = datetime(2026, 5, 1, tzinfo=UTC)
    a.last_seen = datetime(2026, 5, 1, tzinfo=UTC)
    a.is_active = True
    a.asset_metadata = None
    a.created_at = datetime(2026, 5, 1, tzinfo=UTC)
    a.updated_at = datetime(2026, 5, 1, tzinfo=UTC)
    return a


def _override_session(execute_results: list[MagicMock]):
    """Install a get_session + get_current_user override.

    The current-user override is required so that ``get_current_user``'s own
    ``session.execute`` calls (user lookup) don't drain the queued results
    intended for the route under test.
    """
    from app.api.routes.v1.auth import get_current_user
    from app.db.engine import get_session
    from app.db.user import User
    from app.main import app

    queue = list(execute_results)
    fake_session = AsyncMock()

    async def _execute(_stmt):
        if not queue:
            raise AssertionError("session.execute called more times than expected")
        return queue.pop(0)

    fake_session.execute = AsyncMock(side_effect=_execute)
    fake_session.commit = AsyncMock(return_value=None)
    fake_session.add = MagicMock()
    fake_session.flush = AsyncMock(return_value=None)

    async def _gen():
        yield fake_session

    async def _user_override():
        u = MagicMock(spec=User)
        u.id = 1
        u.email = "test@example.com"
        u.role = "admin"
        u.org_id = _ORG_ID
        u.is_active = True
        return u

    app.dependency_overrides[get_session] = _gen
    app.dependency_overrides[get_current_user] = _user_override
    return fake_session


def _clear_overrides():
    from app.api.routes.v1.auth import get_current_user
    from app.db.engine import get_session
    from app.main import app

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# /assets/{id}/findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_findings_returns_empty_when_asset_has_no_software(client: AsyncClient):
    _override_session([_exec_result_scalars([])])
    try:
        with (
            patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
            patch(
                "app.repositories.assets.SqlAssetRepository.get_by_id",
                new=AsyncMock(return_value=_make_asset()),
            ),
        ):
            resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/assets/{_ASSET_ID}/findings")
    finally:
        _clear_overrides()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["asset_id"] == _ASSET_ID
    assert body["total"] == 0
    assert body["items"] == []
    assert "preliminary" in body["note"].lower()


@pytest.mark.asyncio
async def test_findings_404_when_asset_missing(client: AsyncClient):
    with (
        patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.assets.SqlAssetRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/assets/{_ASSET_ID}/findings")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_findings_includes_kev_then_nvd_matches(client: AsyncClient):
    """KEV-matched rows come first; NVD-described rows follow with in_kev=False."""
    software = [_make_software(sid=11, vendor="nginx", product="nginx", version="1.24.0")]

    # Sequence:
    #  1. select(AssetSoftware) → software list
    #  2. KEV join CVE → one row (CVE-2024-1)
    #  3. NVD LIKE %nginx% → CVE-2024-1 (already seen, skipped) + CVE-2024-2
    execute_queue = [
        _exec_result_scalars(software),
        _exec_result_rows(
            [
                (
                    "CVE-2024-1",
                    "nginx",
                    "nginx",
                    9.8,
                    "CRITICAL",
                    "RCE in nginx",
                ),
            ]
        ),
        _exec_result_rows(
            [
                ("CVE-2024-1", 9.8, "CRITICAL", "RCE in nginx"),
                ("CVE-2024-2", 7.5, "HIGH", "DoS in nginx parser"),
            ]
        ),
    ]
    _override_session(execute_queue)
    try:
        with (
            patch(_CHECK_ORG, new=AsyncMock(return_value=None)),
            patch(
                "app.repositories.assets.SqlAssetRepository.get_by_id",
                new=AsyncMock(return_value=_make_asset()),
            ),
        ):
            resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/assets/{_ASSET_ID}/findings")
    finally:
        _clear_overrides()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    items = body["items"]
    # KEV first
    assert items[0]["cve_id"] == "CVE-2024-1"
    assert items[0]["in_kev"] is True
    # NVD second, dedup'd (no second CVE-2024-1)
    assert items[1]["cve_id"] == "CVE-2024-2"
    assert items[1]["in_kev"] is False


# ---------------------------------------------------------------------------
# /inventory/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inventory_health_zero_state(client: AsyncClient):
    """Brand-new org with no inventory yet — all zero, no last upload, no top vendors."""
    execute_queue = [
        _exec_result_scalar_one(0),  # assets_total
        _exec_result_scalar_one(0),  # assets_with_software
        _exec_result_scalar_one(None),  # kev match assets (scalar_one with None coerces to 0)
        _exec_result_first(None),  # last_run
        _exec_result_rows([]),  # top_vendors
    ]
    _override_session(execute_queue)
    try:
        with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
            resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/inventory/health")
    finally:
        _clear_overrides()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "assets_total": 0,
        "assets_with_known_software": 0,
        "assets_with_kev_match": 0,
        "last_inventory_update": None,
        "last_source": None,
        "top_vendors": [],
        "source": "assets_inventory",
    }


@pytest.mark.asyncio
async def test_inventory_health_populated(client: AsyncClient):
    last_run_at = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    execute_queue = [
        _exec_result_scalar_one(10),
        _exec_result_scalar_one(8),
        _exec_result_scalar_one(3),
        _exec_result_first((last_run_at, "csv_upload")),
        _exec_result_rows([("nginx", 5), ("Microsoft", 3), ("openssl", 2)]),
    ]
    _override_session(execute_queue)
    try:
        with patch(_CHECK_ORG, new=AsyncMock(return_value=None)):
            resp = await client.get(f"/api/v1/organizations/{_ORG_ID}/inventory/health")
    finally:
        _clear_overrides()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assets_total"] == 10
    assert body["assets_with_known_software"] == 8
    assert body["assets_with_kev_match"] == 3
    assert body["last_source"] == "csv_upload"
    assert body["last_inventory_update"].startswith("2026-05-20")
    assert body["top_vendors"] == [
        {"vendor": "nginx", "asset_count": 5},
        {"vendor": "Microsoft", "asset_count": 3},
        {"vendor": "openssl", "asset_count": 2},
    ]
