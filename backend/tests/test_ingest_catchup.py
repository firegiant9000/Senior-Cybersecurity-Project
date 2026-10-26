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
) -> SourceState:
    return SourceState(
        source=source,
        trigger=NIGHTLY if scheduled else None,
        has_rows=has_rows,
        last_success_at=success_at or _ago(success_h),
        last_attempt_at=_ago(attempt_h),
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
    assert run.await_args_list[0].kwargs == {"trigger": "catchup"}


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
    monkeypatch.setattr(app_main, "run_sequential_ingest", sequential)
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
    sequential.assert_awaited_once_with(
        ["nvd", "cisa_kev", "ic3"], trigger="startup", recheck=False
    )
    catchup_runner.assert_not_awaited()
