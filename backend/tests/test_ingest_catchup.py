"""Tests for catch-up source selection and execution."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete

import app.api.routes.v1.ingest as ingest_routes
import app.main as app_main
import app.services.ingest_catchup as catchup
from app.core.config import settings
from app.db.engine import AsyncSessionLocal
from app.models.ingest_run import IngestRun
from app.services.ingest_catchup import (
    SourceState,
    attempt_guard,
    hours_since,
    is_stale,
    load_source_states,
    run_catchup,
    run_sequential_ingest,
    scheduled_triggers,
    select_sources,
    stale_thresholds,
)

NOW = datetime(2026, 10, 25, 12, 0)
NIGHTLY = CronTrigger.from_crontab("0 1 * * *", timezone="UTC")


def _ago(hours: float | None) -> datetime | None:
    return None if hours is None else NOW - timedelta(hours=hours)


def _s(
    source: str,
    *,
    scheduled: bool = True,
    has_rows: bool | None = True,
    success_h: float | None = None,
    attempt_h: float | None = None,
    success_at: datetime | None = None,
    failures: int = 0,
    status: str | None = None,
) -> SourceState:
    return SourceState(
        source=source,
        trigger=NIGHTLY if scheduled else None,
        has_rows=has_rows,
        last_success_at=success_at or _ago(success_h),
        last_attempt_at=_ago(attempt_h),
        consecutive_failures=failures,
        latest_status=status,
        latest_started_at=_ago(attempt_h),
    )


def test_never_run_scheduled_source_selected():
    assert select_sources([_s("epss", has_rows=None)], NOW) == ["epss"]


def test_fresh_source_not_selected():
    states = [_s("nvd", success_h=2, attempt_h=2)]
    assert select_sources(states, NOW) == []


def test_missed_firing_selected_even_under_stale_threshold():
    # Last success D-1 01:20, now D 01:30: the 01:00 firing was missed (24 h < 25 h).
    state = _s("nvd", success_at=datetime(2026, 10, 24, 1, 20))
    assert select_sources([state], datetime(2026, 10, 25, 1, 30)) == ["nvd"]


def test_success_after_todays_firing_not_selected():
    state = _s("nvd", success_at=datetime(2026, 10, 25, 1, 20))
    assert select_sources([state], datetime(2026, 10, 25, 23, 0)) == []


def test_success_before_firing_and_firing_passed_selected():
    state = _s("nvd", success_h=12)  # 00:00 today, firing 01:00 already passed
    assert select_sources([state], NOW) == ["nvd"]


def test_firing_must_be_strictly_after_last_success():
    on_firing = datetime(2026, 10, 25, 1, 0)
    assert select_sources([_s("nvd", success_at=on_firing)], NOW) == []
    next_day = datetime(2026, 10, 26, 1, 0)
    assert select_sources([_s("nvd", success_at=on_firing)], next_day) == ["nvd"]


def test_unscheduled_source_with_rows_not_selected():
    states = [_s("ic3", scheduled=False, has_rows=True, success_h=5000)]
    assert select_sources(states, NOW) == []


def test_unscheduled_empty_source_seeded():
    states = [_s("ic3", scheduled=False, has_rows=False)]
    assert select_sources(states, NOW) == ["ic3"]


def test_unscheduled_sources_only_seed():
    states = [
        _s("nvd", scheduled=False, has_rows=False),
        _s("cisa_kev", scheduled=False, has_rows=True, success_h=5000),
        _s("epss", scheduled=False, has_rows=None),
        _s("ic3", scheduled=False, has_rows=True),
        _s("economics", scheduled=False, has_rows=None),
    ]
    assert select_sources(states, NOW) == ["nvd"]


def test_scheduled_empty_table_selected_even_if_fresh():
    states = [_s("nvd", has_rows=False, success_h=1)]
    assert select_sources(states, NOW) == ["nvd"]


def test_order_is_fixed_regardless_of_input():
    states = [
        _s("epss", has_rows=None),
        _s("ic3", scheduled=False, has_rows=False),
        _s("cisa_kev"),
        _s("nvd"),
    ]
    assert select_sources(states, NOW) == ["nvd", "cisa_kev", "epss", "ic3"]


def test_recent_attempt_suppresses_catchup():
    assert select_sources([_s("nvd", success_h=30, attempt_h=0.5)], NOW) == []
    assert select_sources([_s("nvd", success_h=30, attempt_h=1.5)], NOW) == ["nvd"]
    states = [_s("ic3", scheduled=False, has_rows=False, attempt_h=0.5)]
    assert select_sources(states, NOW) == []


@pytest.mark.parametrize(
    ("failures", "expected_hours"), [(0, 1), (1, 2), (2, 4), (3, 8), (4, 16), (5, 24), (10, 24)]
)
def test_attempt_guard_backs_off_and_caps(failures, expected_hours):
    assert attempt_guard(failures) == timedelta(hours=expected_hours)


def test_backoff_guard_applied_in_selection():
    assert select_sources([_s("nvd", success_h=90, attempt_h=1.5, failures=1)], NOW) == []
    assert select_sources([_s("nvd", success_h=90, attempt_h=2.5, failures=1)], NOW) == ["nvd"]
    assert select_sources([_s("nvd", success_h=90, attempt_h=7, failures=3)], NOW) == []
    assert select_sources([_s("nvd", success_h=90, attempt_h=20, failures=10)], NOW) == []
    assert select_sources([_s("nvd", success_h=90, attempt_h=25, failures=10)], NOW) == ["nvd"]


def test_in_progress_run_is_skipped():
    running_30m = _s("nvd", success_h=30, attempt_h=0.5, status="running")
    assert select_sources([running_30m], NOW, running_timeout=timedelta(hours=1)) == []
    # Past the 1 h failure guard but still inside the lock timeout: still live.
    running_90m = _s("nvd", success_h=30, attempt_h=1.5, status="running")
    assert select_sources([running_90m], NOW, running_timeout=timedelta(hours=2)) == []
    running_2h = _s("nvd", success_h=30, attempt_h=2, status="running")
    assert select_sources([running_2h], NOW, running_timeout=timedelta(hours=1)) == ["nvd"]


def test_in_progress_timeout_defaults_to_lock_timeout_setting(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_LOCK_TIMEOUT_SECONDS", 3600)
    assert select_sources([_s("nvd", success_h=30, attempt_h=1.5, status="running")], NOW) == [
        "nvd"
    ]
    monkeypatch.setattr(settings, "INGEST_LOCK_TIMEOUT_SECONDS", 3 * 3600)
    assert select_sources([_s("nvd", success_h=30, attempt_h=1.5, status="running")], NOW) == []


def test_never_succeeded_with_recent_attempt_not_selected():
    assert select_sources([_s("epss", has_rows=None, attempt_h=0.2)], NOW) == []


def test_is_stale_and_hours_since():
    assert is_stale(None, 25) is True
    assert is_stale(26, 25) is True
    assert is_stale(25.0, 25) is False
    assert hours_since(None, NOW) is None
    assert hours_since(NOW - timedelta(minutes=90), NOW) == 1.5


def test_stale_thresholds_reads_settings(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_STALE_HOURS_NVD", 7)
    thresholds = stale_thresholds()
    assert thresholds["nvd"] == 7
    assert set(thresholds) == {"nvd", "cisa_kev", "epss", "ic3", "economics"}


def test_scheduled_triggers(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    assert not any(scheduled_triggers().values())

    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_NVD", "0 1 * * *")
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_IC3", "")
    triggers = scheduled_triggers()
    assert triggers["ic3"] is None
    assert isinstance(triggers["nvd"], CronTrigger)


def test_invalid_cron_is_not_scheduled(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_NVD", "bad cron")
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_KEV", "15 1 * * *")
    triggers = scheduled_triggers()
    assert triggers["nvd"] is None
    assert isinstance(triggers["cisa_kev"], CronTrigger)


def test_scheduled_triggers_read_settings_at_call_time(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_EPSS", "")
    assert scheduled_triggers()["epss"] is None
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_EPSS", "0 2 * * *")
    assert scheduled_triggers()["epss"] is not None


@pytest.mark.asyncio
async def test_load_source_states_reads_runs():
    # Naive UTC with microseconds stripped so values round-trip exactly.
    now = datetime.utcnow().replace(microsecond=0)
    completed = IngestRun(
        id=uuid4(),
        source="economics",
        started_at=now - timedelta(hours=3, minutes=5),
        finished_at=now - timedelta(hours=3),
        status="completed",
    )
    failed = IngestRun(
        id=uuid4(),
        source="economics",
        started_at=now - timedelta(minutes=10),
        finished_at=now - timedelta(minutes=9),
        status="failed",
    )
    run_ids = [completed.id, failed.id]
    async with AsyncSessionLocal() as db:
        try:
            db.add_all([completed, failed])
            await db.commit()
            expected_success = now - timedelta(hours=3)
            expected_attempt = now - timedelta(minutes=10)

            states = {s.source: s for s in await load_source_states(db, {"economics": NIGHTLY})}
            econ = states["economics"]
            assert econ.trigger is NIGHTLY
            assert econ.last_success_at == expected_success
            assert econ.last_attempt_at == expected_attempt
            assert econ.has_rows is None
            assert isinstance(states["nvd"].has_rows, bool)
            assert states["nvd"].trigger is None

            only = await load_source_states(db, {"economics": NIGHTLY}, ["economics"])
            assert [s.source for s in only] == ["economics"]
        finally:
            await db.rollback()
            await db.execute(delete(IngestRun).where(IngestRun.id.in_(run_ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_load_source_states_counts_consecutive_failures_and_latest_row():
    now = datetime.utcnow().replace(microsecond=0)

    def run(source, hours_ago, status):
        started = now - timedelta(hours=hours_ago)
        return IngestRun(
            id=uuid4(),
            source=source,
            started_at=started,
            finished_at=started + timedelta(minutes=1),
            status=status,
        )

    rows = [
        # economics: a failure before the last success does not count; two after do.
        run("economics", 10, "failed"),
        run("economics", 8, "completed"),
        run("economics", 6, "failed"),
        run("economics", 4, "failed"),
        run("economics", 1, "running"),
        # epss: never succeeded, so every failure counts.
        run("epss", 5, "failed"),
        run("epss", 3, "failed"),
        run("epss", 2, "failed"),
    ]
    run_ids = [r.id for r in rows]
    async with AsyncSessionLocal() as db:
        try:
            db.add_all(rows)
            await db.commit()
            states = {s.source: s for s in await load_source_states(db, {})}
            assert states["economics"].consecutive_failures == 2
            assert states["economics"].latest_status == "running"
            assert states["economics"].latest_started_at == now - timedelta(hours=1)
            assert states["epss"].consecutive_failures == 3
            assert states["epss"].latest_status == "failed"
        finally:
            await db.rollback()
            await db.execute(delete(IngestRun).where(IngestRun.id.in_(run_ids)))
            await db.commit()


class _DummySession:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def no_db(monkeypatch):
    """Run catch-up against fake states: no DB, judged at the fixed NOW."""
    monkeypatch.setattr(catchup, "AsyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(catchup, "_utcnow", lambda: NOW)
    monkeypatch.setattr(catchup.settings, "INGEST_CATCHUP_ON_STARTUP", True)
    monkeypatch.setattr(
        catchup, "scheduled_triggers", lambda: dict.fromkeys(catchup.CATCHUP_ORDER, NIGHTLY)
    )


def _fake_loader(monkeypatch, build):
    """Patch load_source_states; ``build(call_index, sources)`` returns the states."""
    calls: list[list[str]] = []

    async def fake(db, triggers, sources=catchup.CATCHUP_ORDER):
        sources = list(sources)
        calls.append(sources)
        return build(len(calls) - 1, sources)

    monkeypatch.setattr(catchup, "load_source_states", fake)
    return calls


async def test_run_catchup_runs_selected_sources_in_order(no_db, monkeypatch):
    _fake_loader(
        monkeypatch,
        lambda i, sources: [
            _s("nvd", success_h=30),
            _s("cisa_kev", success_h=1),
            _s("epss", has_rows=None, success_h=None),
        ],
    )
    runner = AsyncMock()
    monkeypatch.setattr(catchup, "run_sequential_ingest", runner)

    selected = await run_catchup("catchup")

    assert selected == ["nvd", "epss"]
    runner.assert_awaited_once_with(["nvd", "epss"], trigger="catchup", recheck=True)


async def test_run_catchup_disabled_seeds_only(no_db, monkeypatch):
    monkeypatch.setattr(catchup.settings, "INGEST_CATCHUP_ON_STARTUP", False)
    seen: list[dict] = []

    async def fake(db, triggers, sources=catchup.CATCHUP_ORDER):
        seen.append(dict(triggers))
        return [
            _s("nvd", scheduled=False, success_h=30),
            _s("ic3", scheduled=False, has_rows=False),
        ]

    monkeypatch.setattr(catchup, "load_source_states", fake)
    runner = AsyncMock()
    monkeypatch.setattr(catchup, "run_sequential_ingest", runner)

    await run_catchup("startup")

    assert seen == [{}]
    runner.assert_awaited_once_with(["ic3"], trigger="startup", recheck=True)


async def test_run_catchup_nothing_due(no_db, monkeypatch):
    _fake_loader(monkeypatch, lambda i, s: [_s("nvd", success_h=1), _s("cisa_kev", success_h=1)])
    runner = AsyncMock()
    monkeypatch.setattr(catchup, "run_sequential_ingest", runner)

    assert await run_catchup("catchup") == []
    runner.assert_not_awaited()


async def test_recheck_skips_source_that_became_fresh(no_db, monkeypatch):
    """The list was computed with both due; epss is fresh by the time it is reached."""

    def build(call_index, sources):
        if call_index == 0:  # initial selection
            return [_s("nvd", success_h=30), _s("epss", has_rows=None, success_h=30)]
        # Per-source re-check: epss was run by its cron job in the meantime.
        return [
            _s(src, has_rows=None, success_h=30 if src == "nvd" else 1, attempt_h=None)
            for src in sources
        ]

    calls = _fake_loader(monkeypatch, build)
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)

    selected = await run_catchup("catchup")

    assert selected == ["nvd", "epss"]
    assert calls == [list(catchup.CATCHUP_ORDER), ["nvd"], ["epss"]]
    assert [c.args[0] for c in run.await_args_list] == ["nvd"]
    assert run.await_args_list[0].kwargs == {
        "trigger": "catchup",
        "retry_count": settings.INGEST_MAX_RETRIES,
    }


async def test_recheck_skips_source_started_within_guard(no_db, monkeypatch):
    def build(call_index, sources):
        if call_index == 0:
            return [_s("nvd", success_h=30)]
        return [_s("nvd", success_h=30, attempt_h=0.1)]  # a cron run just started

    _fake_loader(monkeypatch, build)
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)

    await run_catchup("startup")

    run.assert_not_awaited()


async def test_run_sequential_ingest_uses_trigger_and_continues(monkeypatch):
    run = AsyncMock(side_effect=[RuntimeError("boom"), None])
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)
    await run_sequential_ingest(["nvd", "epss"], trigger="startup", recheck=False)
    assert [c.args[0] for c in run.await_args_list] == ["nvd", "epss"]
    assert all(c.kwargs == {"trigger": "startup"} for c in run.await_args_list)


@pytest.mark.parametrize("trigger", ["startup", "catchup"])
async def test_catchup_runs_do_not_schedule_retries(no_db, monkeypatch, trigger):
    _fake_loader(monkeypatch, lambda i, s: [_s(src, success_h=30) for src in s])
    monkeypatch.setattr(catchup.settings, "INGEST_MAX_RETRIES", 3)
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)

    await run_sequential_ingest(["nvd"], trigger=trigger, recheck=True)

    assert run.await_args_list[0].kwargs == {"trigger": trigger, "retry_count": 3}


async def test_force_seed_keeps_retry_chain(monkeypatch):
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)
    await catchup.run_forced_seed(["nvd"])
    assert run.await_args_list[0].kwargs == {"trigger": "startup"}


async def test_recheck_error_on_one_source_does_not_abort_the_rest(monkeypatch):
    still_due = AsyncMock(side_effect=[RuntimeError("db blip"), True])
    monkeypatch.setattr(catchup, "_still_due", still_due)
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)

    await run_sequential_ingest(["nvd", "cisa_kev"], trigger="catchup", recheck=True)

    assert [c.args[0] for c in run.await_args_list] == ["cisa_kev"]


async def test_sweep_during_startup_catchup_runs_nothing(no_db, monkeypatch):
    _fake_loader(monkeypatch, lambda i, s: [_s("nvd", success_h=30), _s("cisa_kev", success_h=30)])
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_runner(sources, *, trigger, recheck):
        started.set()
        await release.wait()

    runner = AsyncMock(side_effect=slow_runner)
    monkeypatch.setattr(catchup, "run_sequential_ingest", runner)

    startup_task = asyncio.create_task(run_catchup("startup"))
    await started.wait()
    sweep_result = await asyncio.wait_for(run_catchup("catchup"), timeout=1)
    release.set()
    await startup_task

    assert sweep_result == []
    assert runner.await_count == 1
    assert runner.await_args_list[0].kwargs["trigger"] == "startup"
    # The lock is released afterwards, so the next sweep can run.
    assert await run_catchup("catchup") == ["nvd", "cisa_kev"]


async def test_force_seed_holds_the_catchup_lock(no_db, monkeypatch):
    _fake_loader(monkeypatch, lambda i, s: [_s("nvd", success_h=30)])
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(source, **kwargs):
        started.set()
        await release.wait()

    monkeypatch.setattr(ingest_routes, "_run_ingestion", slow_run)
    seed_task = asyncio.create_task(catchup.run_forced_seed(["nvd"]))
    await started.wait()
    assert await asyncio.wait_for(run_catchup("catchup"), timeout=1) == []
    release.set()
    await seed_task


async def test_run_sequential_ingest_without_recheck_forces_all(monkeypatch):
    run = AsyncMock()
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)
    still_due = AsyncMock(return_value=False)
    monkeypatch.setattr(catchup, "_still_due", still_due)

    await run_sequential_ingest(["nvd", "cisa_kev", "ic3"], trigger="startup", recheck=False)

    assert [c.args[0] for c in run.await_args_list] == ["nvd", "cisa_kev", "ic3"]
    still_due.assert_not_awaited()


@pytest.fixture
def startup(monkeypatch):
    """Patch app.main so _auto_ingest runs without a DB or real ingestors."""
    app_main._background_tasks.clear()
    catchup_runner = AsyncMock()
    sequential = AsyncMock()
    monkeypatch.setattr(app_main, "run_catchup", catchup_runner)
    monkeypatch.setattr(app_main, "run_forced_seed", sequential)
    monkeypatch.setattr(app_main.settings, "FORCE_SEED", False)
    yield catchup_runner, sequential
    app_main._background_tasks.clear()


async def test_auto_ingest_runs_catchup_with_startup_trigger(startup):
    catchup_runner, sequential = startup
    await app_main._auto_ingest()
    await asyncio.gather(*app_main._background_tasks)
    catchup_runner.assert_awaited_once_with("startup")
    sequential.assert_not_awaited()


async def test_force_seed_forces_all_without_recheck(startup, monkeypatch):
    catchup_runner, sequential = startup
    monkeypatch.setattr(app_main.settings, "FORCE_SEED", True)
    await app_main._auto_ingest()
    await asyncio.gather(*app_main._background_tasks)
    sequential.assert_awaited_once_with(["nvd", "cisa_kev", "ic3"])
    catchup_runner.assert_not_awaited()


async def test_startup_task_failure_is_logged(startup, caplog):
    catchup_runner, _ = startup
    catchup_runner.side_effect = RuntimeError("db down")
    with caplog.at_level("ERROR", logger="app.main"):
        await app_main._auto_ingest()
        await asyncio.gather(*app_main._background_tasks, return_exceptions=True)
    assert any("Startup catch-up failed" in r.getMessage() and r.exc_info for r in caplog.records)
