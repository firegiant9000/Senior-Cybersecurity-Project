"""Unit tests for the Month 3 Phase 1 scheduled CPE-backfill job.

Mirrors the matcher-job tests: advisory-lock gating and session lifecycle with
mocked dependencies — no live database required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers import cpe_backfill_job


def _fake_session_factory():
    db = MagicMock()

    @asynccontextmanager
    async def _factory():
        yield db

    return _factory, db


@pytest.mark.asyncio
async def test_skips_when_lock_held():
    factory, _db = _fake_session_factory()
    with (
        patch.object(cpe_backfill_job, "AsyncSessionLocal", factory),
        patch.object(cpe_backfill_job, "try_acquire_lock", AsyncMock(return_value=False)),
        patch.object(cpe_backfill_job, "release_lock", AsyncMock()) as release,
        patch.object(cpe_backfill_job, "backfill_cpe_configurations", AsyncMock()) as backfill,
    ):
        result = await cpe_backfill_job.run_cpe_backfill_sweep()

    assert result == {}
    backfill.assert_not_called()
    release.assert_not_called()


@pytest.mark.asyncio
async def test_runs_with_configured_limit_and_releases():
    factory, db = _fake_session_factory()
    counts = {"checked": 10, "persisted": 7, "criteria": 30, "missing_upstream": 1}
    with (
        patch.object(cpe_backfill_job, "AsyncSessionLocal", factory),
        patch.object(cpe_backfill_job, "try_acquire_lock", AsyncMock(return_value=True)),
        patch.object(cpe_backfill_job, "release_lock", AsyncMock()) as release,
        patch.object(
            cpe_backfill_job, "backfill_cpe_configurations", AsyncMock(return_value=counts)
        ) as backfill,
        patch.object(cpe_backfill_job, "get_settings") as get_settings,
    ):
        get_settings.return_value = MagicMock(NVD_CPE_BACKFILL_MAX_PER_RUN=250)
        result = await cpe_backfill_job.run_cpe_backfill_sweep(trigger="manual")

    assert result == counts
    backfill.assert_awaited_once()
    # The per-run cap from settings is passed through as the limit.
    assert backfill.await_args.kwargs["limit"] == 250
    assert backfill.await_args.args[0] is db
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_releases_on_error():
    factory, _db = _fake_session_factory()
    with (
        patch.object(cpe_backfill_job, "AsyncSessionLocal", factory),
        patch.object(cpe_backfill_job, "try_acquire_lock", AsyncMock(return_value=True)),
        patch.object(cpe_backfill_job, "release_lock", AsyncMock()) as release,
        patch.object(
            cpe_backfill_job,
            "backfill_cpe_configurations",
            AsyncMock(side_effect=RuntimeError("nvd down")),
        ),
        patch.object(cpe_backfill_job, "get_settings") as get_settings,
        pytest.raises(RuntimeError),
    ):
        get_settings.return_value = MagicMock(NVD_CPE_BACKFILL_MAX_PER_RUN=500)
        await cpe_backfill_job.run_cpe_backfill_sweep()

    # Lock must still be released when the backfill blows up.
    release.assert_awaited_once()
