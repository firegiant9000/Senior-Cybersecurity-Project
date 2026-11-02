"""Unit tests for the Month 3 Phase 4 background matcher job.

Exercises the advisory-lock gating, session lifecycle, and sweep fan-out with
mocked dependencies — no live database required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers import matcher_job


def _fake_session_factory():
    """Return (factory, db) where factory() is an async context manager."""
    db = MagicMock()

    @asynccontextmanager
    async def _factory():
        yield db

    return _factory, db


def _fake_engine():
    """Return (engine, lock_conn) where engine.connect() yields the lock conn."""
    conn = MagicMock()

    @asynccontextmanager
    async def _connect():
        yield conn

    engine = MagicMock()
    engine.connect = _connect
    return engine, conn


def test_lock_source_is_per_org():
    assert matcher_job._lock_source(1) != matcher_job._lock_source(2)
    assert matcher_job._lock_source(7) == "matcher_org_7"


@pytest.mark.asyncio
async def test_run_matcher_for_org_skips_when_lock_held():
    factory, _db = _fake_session_factory()
    engine, conn = _fake_engine()
    service = MagicMock()
    service.compute_and_persist_for_org = AsyncMock()

    with (
        patch.object(matcher_job, "AsyncSessionLocal", factory),
        patch.object(matcher_job, "engine", engine),
        patch.object(matcher_job, "try_acquire_lock", AsyncMock(return_value=False)) as acquire,
        patch.object(matcher_job, "release_or_invalidate", AsyncMock()) as release,
        patch.object(matcher_job, "AssetFindingsService", return_value=service),
    ):
        result = await matcher_job.run_matcher_for_org(5, trigger="csv_import")

    assert result == 0
    service.compute_and_persist_for_org.assert_not_called()
    acquire.assert_awaited_once_with(conn, "matcher_org_5")
    # No lock acquired → nothing to release.
    release.assert_not_called()


@pytest.mark.asyncio
async def test_run_matcher_for_org_runs_and_releases_on_lock_conn():
    factory, db = _fake_session_factory()
    engine, conn = _fake_engine()
    service = MagicMock()
    service.compute_and_persist_for_org = AsyncMock(return_value=3)

    with (
        patch.object(matcher_job, "AsyncSessionLocal", factory),
        patch.object(matcher_job, "engine", engine),
        patch.object(matcher_job, "try_acquire_lock", AsyncMock(return_value=True)) as acquire,
        patch.object(matcher_job, "release_or_invalidate", AsyncMock()) as release,
        patch.object(matcher_job, "AssetFindingsService", return_value=service),
    ):
        result = await matcher_job.run_matcher_for_org(5, trigger="csv_import")

    assert result == 3
    service.compute_and_persist_for_org.assert_awaited_once_with(5)
    # Lock is taken and released on the dedicated connection, never the ORM session.
    acquire.assert_awaited_once_with(conn, "matcher_org_5")
    release.assert_awaited_once_with(conn, "matcher_org_5")
    assert conn is not db


@pytest.mark.asyncio
async def test_run_matcher_for_org_releases_on_error():
    factory, _db = _fake_session_factory()
    engine, conn = _fake_engine()
    service = MagicMock()
    service.compute_and_persist_for_org = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch.object(matcher_job, "AsyncSessionLocal", factory),
        patch.object(matcher_job, "engine", engine),
        patch.object(matcher_job, "try_acquire_lock", AsyncMock(return_value=True)),
        patch.object(matcher_job, "release_or_invalidate", AsyncMock()) as release,
        patch.object(matcher_job, "AssetFindingsService", return_value=service),
        pytest.raises(RuntimeError),
    ):
        await matcher_job.run_matcher_for_org(5)

    # Lock must still be released even when the matcher blows up.
    release.assert_awaited_once_with(conn, "matcher_org_5")


@pytest.mark.asyncio
async def test_run_matcher_sweep_runs_each_org():
    with (
        patch.object(matcher_job, "_orgs_needing_match", AsyncMock(return_value=[1, 2, 3])),
        patch.object(matcher_job, "run_matcher_for_org", AsyncMock()) as run_one,
    ):
        await matcher_job.run_matcher_sweep()

    assert run_one.await_count == 3
    org_ids = {call.args[0] for call in run_one.await_args_list}
    assert org_ids == {1, 2, 3}


@pytest.mark.asyncio
async def test_run_matcher_sweep_continues_past_failure():
    with (
        patch.object(matcher_job, "_orgs_needing_match", AsyncMock(return_value=[1, 2])),
        patch.object(
            matcher_job,
            "run_matcher_for_org",
            AsyncMock(side_effect=[RuntimeError("boom"), None]),
        ) as run_one,
    ):
        await matcher_job.run_matcher_sweep()

    # Org 1 failed but the sweep still attempted org 2.
    assert run_one.await_count == 2


@pytest.mark.asyncio
async def test_run_matcher_sweep_noop_when_nothing_stale():
    with (
        patch.object(matcher_job, "_orgs_needing_match", AsyncMock(return_value=[])),
        patch.object(matcher_job, "run_matcher_for_org", AsyncMock()) as run_one,
    ):
        await matcher_job.run_matcher_sweep()

    run_one.assert_not_awaited()
