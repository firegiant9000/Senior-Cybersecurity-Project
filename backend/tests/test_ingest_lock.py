"""Tests for the PG advisory lock helpers in ingest_lock.py."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingest_lock import (
    _lock_key,
    expire_stale_runs,
    release_lock,
    try_acquire_lock,
)

# ── _lock_key ──────────────────────────────────────────────────────────────────


def test_lock_key_known_sources():
    assert _lock_key("nvd") == 0x696E6765_73744E56
    assert _lock_key("cisa_kev") == 0x696E6765_73744B45


def test_lock_key_unknown_source_is_stable():
    key1 = _lock_key("custom_source")
    key2 = _lock_key("custom_source")
    assert key1 == key2
    assert isinstance(key1, int)


# ── try_acquire_lock ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_acquire_lock_success():
    mock_result = MagicMock()
    mock_result.scalar.return_value = True
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await try_acquire_lock(session, "nvd")
    assert result is True


@pytest.mark.asyncio
async def test_acquire_lock_contention():
    mock_result = MagicMock()
    mock_result.scalar.return_value = False
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await try_acquire_lock(session, "nvd")
    assert result is False


# ── release_lock ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_release_lock_calls_unlock():
    session = AsyncMock()
    await release_lock(session, "nvd")
    session.execute.assert_called_once()
    session.commit.assert_called_once()


# ── expire_stale_runs ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_stale_runs_marks_failed():
    stale_run = MagicMock()
    stale_run.status = "running"
    stale_run.started_at = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    stale_run.id = "abc-123"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_run]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.ingest_lock.settings") as mock_settings:
        mock_settings.INGEST_LOCK_TIMEOUT_SECONDS = 7200
        await expire_stale_runs(session, "nvd")

    assert stale_run.status == "failed"
    assert stale_run.finished_at is not None
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_expire_stale_runs_no_stale():
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.ingest_lock.settings") as mock_settings:
        mock_settings.INGEST_LOCK_TIMEOUT_SECONDS = 7200
        await expire_stale_runs(session, "nvd")

    session.commit.assert_not_called()
