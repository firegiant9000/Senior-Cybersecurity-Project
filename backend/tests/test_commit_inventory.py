"""DB tests for ``commit_inventory``'s software upsert (#247).

The software step runs in batches without loading ``AssetSoftware`` ORM objects,
so a 20,000-row agent rescan doesn't hold every row in the session. These pin the
dedupe and ``last_seen`` refresh semantics across batch boundaries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import event, insert, select, update

from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal, engine
from app.db.organization import Organization
from app.db.scan_run import ScanRun
from app.services import inventory_import
from app.services.inventory_import import ParsedRow, commit_inventory

_OLD = datetime(2020, 1, 1, tzinfo=UTC)


def _row(host: str, vendor: str, product: str, version: str | None) -> ParsedRow:
    return ParsedRow(
        hostname=host,
        ip_address=None,
        os_name=None,
        os_version=None,
        vendor=vendor,
        product=product,
        version=version,
        notes=None,
    )


async def _new_org() -> int:
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"commit-inventory-{uuid.uuid4().hex[:8]}")
        session.add(org)
        await session.commit()
        return org.id


async def _software(org_id: int) -> list[AssetSoftware]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AssetSoftware).where(AssetSoftware.org_id == org_id).order_by(AssetSoftware.id)
        )
        return list(result.scalars().all())


@pytest.fixture
def small_batches(monkeypatch):
    monkeypatch.setattr(inventory_import, "SOFTWARE_BATCH_SIZE", 2)


async def test_first_import_inserts_software_across_batches(small_batches):
    org_id = await _new_org()
    rows = [_row("h1", "Acme", f"tool-{i}", "1.0") for i in range(5)]
    rows.append(_row("h1", "ACME", "Tool-0", "1.0"))  # case-insensitive duplicate

    async with AsyncSessionLocal() as session:
        counts = await commit_inventory(
            session, org_id=org_id, rows=rows, scan_run_id=None, source="agent"
        )
        await session.commit()

    assert counts == (1, 5)
    stored = await _software(org_id)
    assert [s.product for s in stored] == [f"tool-{i}" for i in range(5)]
    assert {s.source for s in stored} == {"agent"}
    assert len({s.asset_id for s in stored}) == 1


async def test_reimport_refreshes_existing_and_inserts_new_across_batches(small_batches):
    org_id = await _new_org()
    first = [_row("h1", "Acme", f"tool-{i}", None) for i in range(5)]
    async with AsyncSessionLocal() as session:
        await commit_inventory(session, org_id=org_id, rows=first, scan_run_id=None)
        await session.commit()
        await session.execute(
            update(AssetSoftware).where(AssetSoftware.org_id == org_id).values(last_seen=_OLD)
        )
        await session.commit()

    # Same packages in a different case (a None version matches an empty one), plus two new.
    second = [_row("h1", "ACME", f"TOOL-{i}", "") for i in range(5)]
    second += [_row("h1", "Acme", "new-a", "2.0"), _row("h1", "Acme", "new-b", "2.0")]
    async with AsyncSessionLocal() as session:
        counts = await commit_inventory(session, org_id=org_id, rows=second, scan_run_id=None)
        assert not any(isinstance(obj, AssetSoftware) for obj in session)
        await session.commit()

    assert counts == (1, 7)
    stored = await _software(org_id)
    assert len(stored) == 7
    assert all(s.last_seen > _OLD for s in stored)
    assert sorted(s.product for s in stored) == ["new-a", "new-b"] + [f"tool-{i}" for i in range(5)]


async def test_mixed_null_versions_insert_in_one_statement_per_batch(monkeypatch):
    monkeypatch.setattr(inventory_import, "SOFTWARE_BATCH_SIZE", 10)
    org_id = await _new_org()
    async with AsyncSessionLocal() as session:
        scan_run_id = (
            await session.execute(
                insert(ScanRun).values(org_id=org_id, source="agent").returning(ScanRun.id)
            )
        ).scalar_one()
        await session.commit()

    statements: list[str] = []

    def _count(_conn, _cursor, statement, *_args):  # noqa: ANN001
        if statement.lstrip().upper().startswith("INSERT INTO ASSET_SOFTWARE"):
            statements.append(statement)

    rows = [_row("h1", "Acme", f"tool-{i}", None if i % 2 else "1.0") for i in range(10)]
    event.listen(engine.sync_engine, "before_cursor_execute", _count)
    try:
        async with AsyncSessionLocal() as session:
            await commit_inventory(session, org_id=org_id, rows=rows, scan_run_id=scan_run_id)
            await session.commit()
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count)

    assert len(statements) == 1
    stored = await _software(org_id)
    assert [s.version for s in stored] == [None if i % 2 else "1.0" for i in range(10)]
    assert {s.created_by_scan_run_id for s in stored} == {scan_run_id}


async def test_reimport_leaves_other_assets_software_alone(small_batches):
    org_id = await _new_org()
    async with AsyncSessionLocal() as session:
        await commit_inventory(
            session,
            org_id=org_id,
            rows=[_row("h1", "Acme", "tool", "1.0"), _row("h2", "Acme", "tool", "1.0")],
            scan_run_id=None,
        )
        await session.commit()
        await session.execute(
            update(AssetSoftware).where(AssetSoftware.org_id == org_id).values(last_seen=_OLD)
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await commit_inventory(
            session, org_id=org_id, rows=[_row("h1", "Acme", "tool", "1.0")], scan_run_id=None
        )
        await session.commit()

    stored = await _software(org_id)
    assert len(stored) == 2
    by_host_refreshed = sorted(s.last_seen > _OLD for s in stored)
    assert by_host_refreshed == [False, True]
