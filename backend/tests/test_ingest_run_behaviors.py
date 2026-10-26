"""Unit tests for ingestion trigger, idempotency, and failure retry behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from app.api.routes.v1.ingest import _run_ingestion, trigger_ingestion


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.add = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        # db.get(IngestRun, id) returns the row that was added.
        self.get = AsyncMock(side_effect=lambda *_a, **_k: self.add.call_args.args[0])


class _FakeSessionCtx:
    def __init__(self, session: _FakeAsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeAsyncSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


class _FakeLockConn:
    """Stands in for the dedicated lock AsyncConnection."""

    def __init__(self) -> None:
        self.invalidate = AsyncMock()
        self.close = AsyncMock()


class _FakeEngine:
    def __init__(self, conn: _FakeLockConn | None = None) -> None:
        self.conn = conn or _FakeLockConn()

    async def connect(self) -> _FakeLockConn:
        # Real ``engine.connect()`` returns an awaitable AsyncConnection.
        return self.conn


@pytest.mark.asyncio
async def test_trigger_all_registers_background_tasks_for_each_source():
    bg = BackgroundTasks()
    resp = await trigger_ingestion.__wrapped__(  # type: ignore[attr-defined]
        request=MagicMock(),
        background_tasks=bg,
        source="all",
        _=MagicMock(),
    )
    assert len(resp) == 5
    assert len(bg.tasks) == 5
    assert {item.source for item in resp} == {"nvd", "cisa_kev", "ic3", "economics", "epss"}


@pytest.mark.asyncio
async def test_trigger_single_source_registers_one_task():
    bg = BackgroundTasks()
    resp = await trigger_ingestion.__wrapped__(  # type: ignore[attr-defined]
        request=MagicMock(),
        background_tasks=bg,
        source="nvd",
        _=MagicMock(),
    )
    assert len(resp) == 1
    assert resp[0].source == "nvd"
    assert len(bg.tasks) == 1


@pytest.mark.asyncio
async def test_run_ingestion_skips_when_lock_held():
    fake_session = _FakeAsyncSession()
    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=_FakeEngine()),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=False)),
        patch("app.services.ingest_lock.release_lock", new=AsyncMock()),
        patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock()),
    ):
        await _run_ingestion("nvd", trigger="manual")

    assert fake_session.add.call_count == 1
    skipped_run = fake_session.add.call_args.args[0]
    assert skipped_run.status == "skipped"
    assert skipped_run.skipped_reason == "Lock held by a concurrent run"


@pytest.mark.asyncio
async def test_run_ingestion_skip_path_closes_lock_conn_before_writing_skipped_row():
    """The lock connection must go back to the pool before the session is used again
    for the skipped row, so a burst of skipped triggers never holds one connection
    while waiting for a second."""
    events: list[str] = []
    fake_session = _FakeAsyncSession()
    fake_session.add.side_effect = lambda *_a, **_k: events.append("add")
    fake_session.commit.side_effect = lambda *_a, **_k: events.append("commit")
    fake_engine = _FakeEngine()
    fake_engine.conn.close.side_effect = lambda *_a, **_k: events.append("lock_closed")

    async def _acquire(*_a, **_k):  # noqa: ANN002, ANN003
        events.append("acquire")
        return False

    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=fake_engine),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=_acquire),
        patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock()),
    ):
        await _run_ingestion("nvd", trigger="manual")

    # expire_stale_runs' session work is committed before the lock connection opens.
    assert events == ["commit", "acquire", "lock_closed", "add", "commit"]


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["startup", "catchup"])
async def test_run_ingestion_catchup_skip_writes_no_skipped_row(trigger):
    fake_session = _FakeAsyncSession()
    fake_engine = _FakeEngine()
    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=fake_engine),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=False)),
        patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock()) as dispatch,
    ):
        await _run_ingestion("nvd", trigger=trigger)

    fake_session.add.assert_not_called()
    dispatch.assert_not_called()
    fake_engine.conn.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["manual", "scheduled"])
async def test_run_ingestion_manual_and_scheduled_skip_still_write_skipped_row(trigger):
    fake_session = _FakeAsyncSession()
    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=_FakeEngine()),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=False)),
    ):
        await _run_ingestion("nvd", trigger=trigger)

    fake_session.add.assert_called_once()
    assert fake_session.add.call_args.args[0].status == "skipped"


@pytest.mark.asyncio
async def test_run_ingestion_failure_schedules_retry():
    fake_session = _FakeAsyncSession()

    def _capture_and_close_retry(coro):
        coro.close()
        return MagicMock()

    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=_FakeEngine()),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=True)),
        patch("app.services.ingest_lock.release_lock", new=AsyncMock()),
        patch(
            "app.api.routes.v1.ingest._dispatch_ingestor",
            new=AsyncMock(side_effect=RuntimeError("source unreachable")),
        ),
        patch(
            "app.api.routes.v1.ingest.asyncio.create_task",
            side_effect=_capture_and_close_retry,
        ) as create_task,
        patch("app.api.routes.v1.ingest.settings") as mock_settings,
    ):
        mock_settings.INGEST_MAX_RETRIES = 2
        await _run_ingestion("nvd", trigger="scheduled", retry_count=0)

    run_obj = fake_session.add.call_args.args[0]
    assert run_obj.status == "failed"
    assert "source unreachable" in (run_obj.error_message or "")
    create_task.assert_called_once()


@pytest.mark.asyncio
async def test_run_ingestion_failure_exhausted_retries_does_not_schedule():
    fake_session = _FakeAsyncSession()
    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=_FakeEngine()),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=True)),
        patch("app.services.ingest_lock.release_lock", new=AsyncMock()),
        patch(
            "app.api.routes.v1.ingest._dispatch_ingestor",
            new=AsyncMock(side_effect=RuntimeError("source unreachable")),
        ),
        patch("app.api.routes.v1.ingest.asyncio.create_task") as create_task,
        patch("app.api.routes.v1.ingest.settings") as mock_settings,
    ):
        mock_settings.INGEST_MAX_RETRIES = 1
        await _run_ingestion("nvd", trigger="scheduled", retry_count=1)

    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_run_ingestion_releases_lock_on_lock_conn_and_invalidates_on_failure():
    fake_session = _FakeAsyncSession()
    fake_engine = _FakeEngine()
    release = AsyncMock(side_effect=RuntimeError("conn gone"))
    with (
        patch(
            "app.api.routes.v1.ingest.AsyncSessionLocal", return_value=_FakeSessionCtx(fake_session)
        ),
        patch("app.api.routes.v1.ingest.engine", new=fake_engine),
        patch("app.services.ingest_lock.expire_stale_runs", new=AsyncMock()),
        patch("app.services.ingest_lock.try_acquire_lock", new=AsyncMock(return_value=True)),
        patch("app.services.ingest_lock.release_lock", new=release),
        patch("app.api.routes.v1.ingest._dispatch_ingestor", new=AsyncMock(return_value=1)),
    ):
        await _run_ingestion("nvd", trigger="manual")

    release.assert_awaited_once_with(fake_engine.conn, "nvd")
    fake_engine.conn.invalidate.assert_awaited_once()
