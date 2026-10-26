"""Catch-up source selection for ingest on process start.

Decides which sources ``_auto_ingest`` should run: empty tables are seeded,
and scheduled sources that have gone stale are caught up. All datetimes are
naive UTC, matching ``IngestRun`` columns written with ``datetime.utcnow()``.
"""

import datetime
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CVE, KEV, IC3Incident
from app.models.ingest_run import IngestRun

# Fixed catch-up order: the CVE/KEV tables feed the others.
CATCHUP_ORDER: tuple[str, ...] = ("nvd", "cisa_kev", "epss", "ic3", "economics")

# A source attempted this recently (success or failure) is not re-run, so a
# crash-looping process cannot hammer an upstream API.
RECENT_ATTEMPT_GUARD = datetime.timedelta(hours=1)

# Sources whose table can be checked for rows; the rest have no seed table.
_SEED_TABLES = {"nvd": CVE, "cisa_kev": KEV, "ic3": IC3Incident}


@dataclass(frozen=True)
class SourceState:
    """What the catch-up decision needs to know about one source."""

    source: str
    scheduled: bool
    has_rows: bool | None  # None: no seed table for this source
    last_success_at: datetime.datetime | None
    last_attempt_at: datetime.datetime | None


def stale_thresholds() -> dict[str, int]:
    """Staleness threshold in hours per source, read from settings at call time."""
    return {
        "nvd": settings.INGEST_STALE_HOURS_NVD,
        "cisa_kev": settings.INGEST_STALE_HOURS_KEV,
        "ic3": settings.INGEST_STALE_HOURS_IC3,
        "economics": settings.INGEST_STALE_HOURS_ECON,
        "epss": settings.INGEST_STALE_HOURS_EPSS,
    }


def hours_since(finished_at: datetime.datetime | None, now: datetime.datetime) -> float | None:
    """Hours between ``finished_at`` and ``now``, or None if there is no timestamp."""
    if finished_at is None:
        return None
    return (now - finished_at).total_seconds() / 3600


def is_stale(hours_ago: float | None, threshold_hours: int) -> bool:
    """True when a source has never succeeded or its last success is too old."""
    return hours_ago is None or hours_ago > threshold_hours


def select_sources(
    states: Iterable[SourceState],
    thresholds: Mapping[str, int],
    now: datetime.datetime,
) -> list[str]:
    """Return the sources to ingest, in ``CATCHUP_ORDER``.

    A source is due when its table is empty (seed), or when it is scheduled and
    stale. Either way it is skipped if attempted within ``RECENT_ATTEMPT_GUARD``.
    """
    due: set[str] = set()
    for state in states:
        if state.source not in CATCHUP_ORDER:
            continue
        seed = state.has_rows is False
        stale = state.scheduled and is_stale(
            hours_since(state.last_success_at, now), thresholds[state.source]
        )
        if not (seed or stale):
            continue
        if state.last_attempt_at is not None and now - state.last_attempt_at < RECENT_ATTEMPT_GUARD:
            continue
        due.add(state.source)
    return [source for source in CATCHUP_ORDER if source in due]


def scheduled_sources() -> dict[str, bool]:
    """Which sources have a cron schedule that will actually run."""
    crons = {
        "nvd": settings.INGEST_SCHEDULE_NVD,
        "cisa_kev": settings.INGEST_SCHEDULE_KEV,
        "ic3": settings.INGEST_SCHEDULE_IC3,
        "economics": settings.INGEST_SCHEDULE_ECONOMICS,
        "epss": settings.INGEST_SCHEDULE_EPSS,
    }
    return {source: settings.SCHEDULER_ENABLED and bool(cron) for source, cron in crons.items()}


async def load_source_states(db: AsyncSession, scheduled: Mapping[str, bool]) -> list[SourceState]:
    """Read last success/attempt times and table emptiness for every source."""
    success_rows = await db.execute(
        select(IngestRun.source, func.max(IngestRun.finished_at))
        .where(IngestRun.status == "completed")
        .group_by(IngestRun.source)
    )
    last_success = dict(success_rows.all())

    attempt_rows = await db.execute(
        select(IngestRun.source, func.max(IngestRun.started_at)).group_by(IngestRun.source)
    )
    last_attempt = dict(attempt_rows.all())

    states: list[SourceState] = []
    for source in CATCHUP_ORDER:
        model = _SEED_TABLES.get(source)
        has_rows: bool | None = None
        if model is not None:
            has_rows = bool(await db.scalar(select(select(model).exists())))
        states.append(
            SourceState(
                source=source,
                scheduled=scheduled.get(source, False),
                has_rows=has_rows,
                last_success_at=last_success.get(source),
                last_attempt_at=last_attempt.get(source),
            )
        )
    return states
