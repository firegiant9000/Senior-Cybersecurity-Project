"""Tests for catch-up source selection."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete

import app.main as app_main
from app.core.config import settings
from app.db.engine import AsyncSessionLocal
from app.models.ingest_run import IngestRun
from app.services.ingest_catchup import (
    SourceState,
    hours_since,
    is_stale,
    load_source_states,
    scheduled_sources,
    select_sources,
    stale_thresholds,
)

NOW = datetime(2026, 10, 25, 12, 0)
THRESHOLDS = {"nvd": 25, "cisa_kev": 25, "epss": 49, "ic3": 168, "economics": 168}


def _ago(hours: float | None) -> datetime | None:
    return None if hours is None else NOW - timedelta(hours=hours)


def _s(
    source: str,
    *,
    scheduled: bool = True,
    has_rows: bool | None = True,
    success_h: float | None = None,
    attempt_h: float | None = None,
) -> SourceState:
    return SourceState(
        source=source,
        scheduled=scheduled,
        has_rows=has_rows,
        last_success_at=_ago(success_h),
        last_attempt_at=_ago(attempt_h),
    )


def test_never_run_scheduled_source_selected():
    assert select_sources([_s("epss", has_rows=None)], THRESHOLDS, NOW) == ["epss"]


def test_fresh_source_not_selected():
    states = [_s("nvd", success_h=2, attempt_h=2)]
    assert select_sources(states, THRESHOLDS, NOW) == []


def test_stale_source_selected():
    assert select_sources([_s("nvd", success_h=26)], THRESHOLDS, NOW) == ["nvd"]
    assert select_sources([_s("nvd", success_h=25.0)], THRESHOLDS, NOW) == []


def test_unscheduled_source_with_rows_not_selected():
    states = [_s("ic3", scheduled=False, has_rows=True, success_h=5000)]
    assert select_sources(states, THRESHOLDS, NOW) == []


def test_unscheduled_empty_source_seeded():
    states = [_s("ic3", scheduled=False, has_rows=False)]
    assert select_sources(states, THRESHOLDS, NOW) == ["ic3"]


def test_unscheduled_sources_only_seed():
    states = [
        _s("nvd", scheduled=False, has_rows=False),
        _s("cisa_kev", scheduled=False, has_rows=True, success_h=5000),
        _s("epss", scheduled=False, has_rows=None),
        _s("ic3", scheduled=False, has_rows=True),
        _s("economics", scheduled=False, has_rows=None),
    ]
    assert select_sources(states, THRESHOLDS, NOW) == ["nvd"]


def test_scheduled_empty_table_selected_even_if_fresh():
    states = [_s("nvd", has_rows=False, success_h=1)]
    assert select_sources(states, THRESHOLDS, NOW) == ["nvd"]


def test_order_is_fixed_regardless_of_input():
    states = [
        _s("epss", has_rows=None),
        _s("ic3", scheduled=False, has_rows=False),
        _s("cisa_kev"),
        _s("nvd"),
    ]
    assert select_sources(states, THRESHOLDS, NOW) == ["nvd", "cisa_kev", "epss", "ic3"]


def test_recent_attempt_suppresses_catchup():
    assert select_sources([_s("nvd", success_h=30, attempt_h=0.5)], THRESHOLDS, NOW) == []
    assert select_sources([_s("nvd", success_h=30, attempt_h=1.5)], THRESHOLDS, NOW) == ["nvd"]
    states = [_s("ic3", scheduled=False, has_rows=False, attempt_h=0.5)]
    assert select_sources(states, THRESHOLDS, NOW) == []


def test_is_stale_and_hours_since():
    assert is_stale(None, 25) is True
    assert hours_since(None, NOW) is None
    assert hours_since(NOW - timedelta(minutes=90), NOW) == 1.5


def test_stale_thresholds_reads_settings(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_STALE_HOURS_NVD", 7)
    thresholds = stale_thresholds()
    assert thresholds["nvd"] == 7
    assert set(thresholds) == {"nvd", "cisa_kev", "epss", "ic3", "economics"}


def test_scheduled_sources(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    assert not any(scheduled_sources().values())

    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_NVD", "0 1 * * *")
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_IC3", "")
    sched = scheduled_sources()
    assert sched["ic3"] is False
    assert sched["nvd"] is True


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

            states = {s.source: s for s in await load_source_states(db, {"economics": True})}
            econ = states["economics"]
            assert econ.scheduled is True
            assert econ.last_success_at == expected_success
            assert econ.last_attempt_at == expected_attempt
            assert econ.has_rows is None
            assert isinstance(states["nvd"].has_rows, bool)
            assert states["nvd"].scheduled is False
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
def startup(monkeypatch):
    """Patch app.main so _auto_ingest runs without a DB or real ingestors."""
    app_main._background_tasks.clear()
    runner = AsyncMock()
    monkeypatch.setattr(app_main, "_run_sequential_ingest", runner)
    monkeypatch.setattr(app_main, "AsyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(app_main.settings, "FORCE_SEED", False)
    monkeypatch.setattr(app_main.settings, "INGEST_CATCHUP_ON_STARTUP", True)
    yield runner
    app_main._background_tasks.clear()


def _patch_states(monkeypatch, build):
    """Patch load_source_states; ``build(scheduled)`` returns the states."""
    seen: list[dict[str, bool]] = []

    async def fake(db, scheduled):
        seen.append(dict(scheduled))
        return build(scheduled)

    monkeypatch.setattr(app_main, "load_source_states", fake)
    monkeypatch.setattr(app_main, "scheduled_sources", lambda: dict.fromkeys(THRESHOLDS, True))
    monkeypatch.setattr(app_main, "stale_thresholds", lambda: THRESHOLDS)
    return seen


async def test_auto_ingest_runs_selected_sources_in_order(startup, monkeypatch):
    _patch_states(
        monkeypatch,
        lambda sched: [
            _s("nvd", success_h=30),
            _s("cisa_kev", success_h=1),
            _s("epss", has_rows=None, success_h=None),
        ],
    )
    await app_main._auto_ingest()
    await asyncio.gather(*app_main._background_tasks)
    startup.assert_awaited_once_with(["nvd", "epss"])


async def test_auto_ingest_catchup_disabled_seeds_only(startup, monkeypatch):
    monkeypatch.setattr(app_main.settings, "INGEST_CATCHUP_ON_STARTUP", False)
    seen = _patch_states(
        monkeypatch,
        lambda sched: [
            _s("nvd", scheduled=sched.get("nvd", False), success_h=30),
            _s("ic3", scheduled=sched.get("ic3", False), has_rows=False),
        ],
    )
    await app_main._auto_ingest()
    await asyncio.gather(*app_main._background_tasks)
    assert not any(seen[0].values())
    startup.assert_awaited_once_with(["ic3"])


async def test_auto_ingest_nothing_due_creates_no_task(startup, monkeypatch):
    _patch_states(monkeypatch, lambda sched: [_s("nvd", success_h=1), _s("cisa_kev", success_h=1)])
    await app_main._auto_ingest()
    startup.assert_not_awaited()
    assert not app_main._background_tasks


async def test_force_seed_unchanged(startup, monkeypatch):
    monkeypatch.setattr(app_main.settings, "FORCE_SEED", True)
    seen = _patch_states(monkeypatch, lambda sched: [])
    await app_main._auto_ingest()
    await asyncio.gather(*app_main._background_tasks)
    startup.assert_awaited_once_with(["nvd", "cisa_kev", "ic3"])
    assert seen == []


async def test_run_sequential_ingest_uses_startup_trigger_and_continues(monkeypatch):
    import app.api.routes.v1.ingest as ingest_routes

    run = AsyncMock(side_effect=[RuntimeError("boom"), None])
    monkeypatch.setattr(ingest_routes, "_run_ingestion", run)
    await app_main._run_sequential_ingest(["nvd", "epss"])
    assert [c.args[0] for c in run.await_args_list] == ["nvd", "epss"]
    assert all(c.kwargs == {"trigger": "startup"} for c in run.await_args_list)
