"""Tests for catch-up source selection."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

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
