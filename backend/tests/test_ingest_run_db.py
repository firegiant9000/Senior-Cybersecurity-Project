"""DB-backed tests for ``_run_ingestion`` (real Postgres): scheduler timestamp,
failure recovery after a DB-level error, and advisory-lock release under a pool."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.routes.v1.ingest import _run_ingestion
from app.core.config import settings
from app.db.engine import AsyncSessionLocal, engine
from app.models.ingest_run import IngestRun
from app.services.ingest_lock import _lock_key
from app.workers.scheduler import scheduler

SOURCE = "nvd"


@pytest_asyncio.fixture
async def paused_scheduler() -> AsyncIterator[None]:
    """Register a real ``ingest_nvd`` job so ``job.next_run_time`` is populated."""
    started_here = not scheduler.running
    if started_here:
        scheduler.start(paused=True)
    scheduler.add_job(
        AsyncMock(),
        CronTrigger(hour=3, minute=0, timezone="UTC"),
        id=f"ingest_{SOURCE}",
        replace_existing=True,
    )
    try:
        yield
    finally:
        if scheduler.get_job(f"ingest_{SOURCE}"):
            scheduler.remove_job(f"ingest_{SOURCE}")
        if started_here:
            scheduler.shutdown(wait=False)


async def _latest_run() -> IngestRun:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IngestRun)
            .where(IngestRun.source == SOURCE)
            .order_by(IngestRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one()


async def _advisory_lock_holders(source: str) -> int:
    key = _lock_key(source)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objsubid = 1 "
                "AND classid::bigint = :c AND objid::bigint = :o"
            ),
            {"c": key >> 32, "o": key & 0xFFFFFFFF},
        )
        return int(result.scalar_one())


async def _warm_pool(n: int = 3) -> None:
    """Park several connections in the pool so checkouts rotate between them."""
    conns = [await engine.connect() for _ in range(n)]
    for c in conns:
        await c.execute(text("SELECT 1"))
    for c in conns:
        await c.close()


@pytest.mark.asyncio
async def test_scheduled_run_stores_naive_next_scheduled_at(paused_scheduler):
    with patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock(return_value=5)):
        await _run_ingestion(SOURCE, trigger="scheduled")

    run = await _latest_run()
    assert run.status == "completed"
    assert run.records_ingested == 5
    assert run.next_scheduled_at is not None
    assert run.next_scheduled_at.tzinfo is None


@pytest.mark.asyncio
async def test_db_level_failure_records_failed_and_schedules_retry(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_MAX_RETRIES", 2)

    async def _boom(source: str, db) -> int:  # noqa: ANN001
        try:
            await db.execute(text("SELECT 1/0"))  # aborts the transaction
        except Exception:  # noqa: BLE001
            pass
        raise IntegrityError("stmt", {}, Exception("constraint violated"))

    def _close_coro(coro):  # noqa: ANN001
        coro.close()
        return MagicMock()

    # Replace the module's ``asyncio`` reference only: patching the global
    # ``asyncio.create_task`` would break SQLAlchemy's own task handling.
    fake_asyncio = MagicMock()
    fake_asyncio.create_task.side_effect = _close_coro
    ct = fake_asyncio.create_task
    with (
        patch("app.api.routes.v1.ingest._dispatch_ingestor", new=_boom),
        patch("app.api.routes.v1.ingest.asyncio", new=fake_asyncio),
    ):
        await _run_ingestion(SOURCE, trigger="scheduled")

    run = await _latest_run()
    assert run.status == "failed"
    assert run.error_message
    assert run.finished_at is not None
    ct.assert_called_once()


@pytest.mark.asyncio
async def test_lock_released_after_success_with_multiple_pooled_connections():
    await _warm_pool()
    held = AsyncSessionLocal()
    await held.execute(text("SELECT 1"))  # keep another connection checked out
    try:
        with patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock(return_value=1)):
            await _run_ingestion(SOURCE, trigger="manual")
        assert await _advisory_lock_holders(SOURCE) == 0
    finally:
        await held.close()


@pytest.mark.asyncio
async def test_lock_released_after_failure_with_multiple_pooled_connections(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_MAX_RETRIES", 0)
    await _warm_pool()
    held = AsyncSessionLocal()
    await held.execute(text("SELECT 1"))
    try:
        with patch(
            "app.api.routes.v1.ingest._dispatch_ingestor",
            new=AsyncMock(side_effect=RuntimeError("nope")),
        ):
            await _run_ingestion(SOURCE, trigger="manual")
        assert await _advisory_lock_holders(SOURCE) == 0
        run = await _latest_run()
        assert run.status == "failed"
    finally:
        await held.close()


@pytest.mark.asyncio
async def test_concurrent_run_is_skipped_while_lock_held_then_runs_after_release():
    key = _lock_key(SOURCE)
    async with engine.connect() as other:
        got = await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
        assert got.scalar_one() is True
        try:
            with patch(
                "app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock(return_value=1)
            ) as dispatch:
                await _run_ingestion(SOURCE, trigger="manual")
            dispatch.assert_not_called()
            assert (await _latest_run()).status == "skipped"
        finally:
            await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            await other.commit()

    with patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock(return_value=2)):
        await _run_ingestion(SOURCE, trigger="manual")
    assert (await _latest_run()).status == "completed"
