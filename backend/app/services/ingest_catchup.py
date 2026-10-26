"""Catch-up source selection and execution for ingest.

Decides which sources to run outside their cron firing: empty tables are
seeded, and scheduled sources that missed a firing are caught up. It runs on
process start (``trigger="startup"``) and from the hourly ``catchup_sweep``
scheduler job (``trigger="catchup"``), both through ``run_catchup``.

A scheduled source has missed a firing when it has never succeeded, or when the
first cron firing strictly after its last success is already in the past. That
catches a run killed by a deploy or crash shortly after its slot, which a
"older than N hours" threshold would miss for most of a day. A source attempted
within ``RECENT_ATTEMPT_GUARD`` is never re-run, so a crash-looping process
cannot hammer an upstream API.

All datetimes are naive UTC, matching ``IngestRun`` columns written with
``datetime.utcnow()``; they are made timezone-aware only to ask the cron
trigger for its next firing.
"""

import datetime
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.engine import AsyncSessionLocal
from app.db.models import CVE, KEV, IC3Incident
from app.models.ingest_run import IngestRun
from app.workers.scheduler import source_cron_exprs

_log = logging.getLogger(__name__)

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
    trigger: CronTrigger | None  # None: not scheduled (disabled, empty or invalid cron)
    has_rows: bool | None  # None: no seed table for this source
    last_success_at: datetime.datetime | None
    last_attempt_at: datetime.datetime | None


def stale_thresholds() -> dict[str, int]:
    """Staleness threshold in hours per source, read from settings at call time.

    Used by ``/ingest/health``; catch-up itself uses the cron schedule instead.
    """
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


def _missed_firing(
    trigger: CronTrigger, last_success_at: datetime.datetime | None, now: datetime.datetime
) -> bool:
    """True when the source never succeeded or a cron firing since then has passed."""
    if last_success_at is None:
        return True
    # +1 microsecond: the trigger returns the first firing at or after its start,
    # and the firing must be strictly after the last success.
    start = last_success_at.replace(tzinfo=datetime.UTC) + datetime.timedelta(microseconds=1)
    next_fire = trigger.get_next_fire_time(None, start)
    return next_fire is not None and next_fire <= now.replace(tzinfo=datetime.UTC)


def select_sources(states: Iterable[SourceState], now: datetime.datetime) -> list[str]:
    """Return the sources to ingest, in ``CATCHUP_ORDER``.

    A source is due when its table is empty (seed), or when it is scheduled and
    has missed a cron firing. Either way it is skipped if attempted within
    ``RECENT_ATTEMPT_GUARD``.
    """
    due: set[str] = set()
    for state in states:
        if state.source not in CATCHUP_ORDER:
            continue
        seed = state.has_rows is False
        missed = state.trigger is not None and _missed_firing(
            state.trigger, state.last_success_at, now
        )
        if not (seed or missed):
            continue
        if state.last_attempt_at is not None and now - state.last_attempt_at < RECENT_ATTEMPT_GUARD:
            continue
        due.add(state.source)
    return [source for source in CATCHUP_ORDER if source in due]


def scheduled_triggers() -> dict[str, CronTrigger | None]:
    """Cron trigger per source, or None when the source will not actually run.

    Reads the same call-time helper as ``init_scheduler``, so catch-up and the
    scheduler cannot disagree. An empty or invalid cron counts as unscheduled.
    """
    triggers: dict[str, CronTrigger | None] = {}
    for source, cron in source_cron_exprs().items():
        trigger: CronTrigger | None = None
        if settings.SCHEDULER_ENABLED and cron:
            try:
                trigger = CronTrigger.from_crontab(cron, timezone="UTC")
            except (ValueError, TypeError):
                _log.warning("Invalid cron for %s (%r) — treated as unscheduled", source, cron)
        triggers[source] = trigger
    return triggers


async def load_source_states(
    db: AsyncSession,
    triggers: Mapping[str, CronTrigger | None],
    sources: Iterable[str] = CATCHUP_ORDER,
) -> list[SourceState]:
    """Read last success/attempt times and table emptiness for the given sources."""
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
    for source in sources:
        model = _SEED_TABLES.get(source)
        has_rows: bool | None = None
        if model is not None:
            has_rows = bool(await db.scalar(select(select(model).exists())))
        states.append(
            SourceState(
                source=source,
                trigger=triggers.get(source),
                has_rows=has_rows,
                last_success_at=last_success.get(source),
                last_attempt_at=last_attempt.get(source),
            )
        )
    return states


def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _active_triggers() -> dict[str, CronTrigger | None]:
    """Triggers to judge staleness with; none when catch-up is off (seed only)."""
    return scheduled_triggers() if settings.INGEST_CATCHUP_ON_STARTUP else {}


async def _still_due(source: str) -> bool:
    """Re-load one source's state and re-apply the catch-up rule."""
    async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
        states = await load_source_states(db, _active_triggers(), [source])
    return bool(select_sources(states, _utcnow()))


async def run_sequential_ingest(sources: list[str], *, trigger: str, recheck: bool = True) -> None:
    """Run ingestion for each source one at a time to avoid DB conflicts.

    With ``recheck`` each source is re-evaluated just before it runs and skipped
    if it is no longer due, since earlier sources can take a long time and the
    scheduler (or another instance) may have run it meanwhile. FORCE_SEED passes
    ``recheck=False`` to force every source.
    """
    from app.api.routes.v1.ingest import _run_ingestion

    for src in sources:
        if recheck and not await _still_due(src):
            _log.info("Skipping %s catch-up — no longer due", src)
            continue
        _log.info("Starting %s ingestion...", src)
        try:
            await _run_ingestion(src, trigger=trigger)
        except Exception:  # noqa: BLE001
            # Errors are already logged and persisted by _run_ingestion; continue
            # to the next source rather than aborting the whole sequence.
            pass


async def run_catchup(trigger: str) -> list[str]:
    """Select due sources and ingest them sequentially; return what was selected.

    Shared by process start (``"startup"``) and the hourly sweep (``"catchup"``).
    With INGEST_CATCHUP_ON_STARTUP=false only empty tables are seeded.
    """
    async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
        states = await load_source_states(db, _active_triggers())
    selected = select_sources(states, _utcnow())

    if not selected:
        # The hourly sweep is mostly a no-op; keep it out of the info log.
        log = _log.info if trigger == "startup" else _log.debug
        log("All data sources populated and fresh — nothing to catch up (%s)", trigger)
        return []

    _log.info("Catching up (%s): %s", trigger, selected)
    await run_sequential_ingest(selected, trigger=trigger, recheck=True)
    return selected
