"""Catch-up source selection and execution for ingest.

Decides which sources to run outside their cron firing: empty tables are
seeded, and scheduled sources that missed a firing are caught up. It runs on
process start (``trigger="startup"``) and from the hourly ``catchup_sweep``
scheduler job (``trigger="catchup"``), both through ``run_catchup``.

A scheduled source has missed a firing when it has never succeeded, or when the
first cron firing strictly after its last success is already in the past. That
catches a run killed by a deploy or crash shortly after its slot, which a
"older than N hours" threshold would miss for most of a day. A source attempted
within its guard is never re-run, so a crash-looping process cannot hammer an
upstream API. The guard is ``RECENT_ATTEMPT_GUARD`` (1 h) doubled per
consecutive failed run since the last success, capped at ``MAX_ATTEMPT_GUARD``
(24 h). A source whose latest run is still ``running`` and younger than
``INGEST_LOCK_TIMEOUT_SECONDS`` is skipped, so a live run is never expired.
Catch-up attempts do not schedule ``_run_ingestion`` retries; the next catch-up
is the retry. Only one catch-up runs at a time: a sweep firing while the
startup catch-up is in flight returns immediately.

All datetimes are naive UTC, matching ``IngestRun`` columns written with
``datetime.utcnow()``; they are made timezone-aware only to ask the cron
trigger for its next firing.
"""

import asyncio
import datetime
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, or_, select
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
# crash-looping process cannot hammer an upstream API. Each consecutive failure
# doubles the guard (see ``attempt_guard``) up to ``MAX_ATTEMPT_GUARD``.
RECENT_ATTEMPT_GUARD = datetime.timedelta(hours=1)
MAX_ATTEMPT_GUARD = datetime.timedelta(hours=24)

# Single-flight: only one catch-up (startup, sweep or FORCE_SEED) runs at a time,
# so NVD and KEV never ingest concurrently (duplicate key conflicts).
_catchup_lock = asyncio.Lock()

# Triggers whose failures are retried by the next catch-up instead of by
# ``_run_ingestion``'s own retry chain.
_CATCHUP_TRIGGERS = frozenset({"startup", "catchup"})

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
    # Failed runs since the last completed run (0 when none); drives the backoff.
    consecutive_failures: int = 0
    # Status and start time of the most recent run, to spot one still in progress.
    latest_status: str | None = None
    latest_started_at: datetime.datetime | None = None


def attempt_guard(consecutive_failures: int) -> datetime.timedelta:
    """Minimum gap between catch-up attempts: 1 h doubling per failure, capped at 24 h."""
    n = max(0, min(consecutive_failures, 5))  # 2**5 h already exceeds the cap
    return min(RECENT_ATTEMPT_GUARD * 2**n, MAX_ATTEMPT_GUARD)


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


def select_sources(
    states: Iterable[SourceState],
    now: datetime.datetime,
    running_timeout: datetime.timedelta | None = None,
) -> list[str]:
    """Return the sources to ingest, in ``CATCHUP_ORDER``.

    A source is due when its table is empty (seed), or when it is scheduled and
    has missed a cron firing. Either way it is skipped if attempted within its
    backoff guard (``attempt_guard``), or if its latest run is ``running`` and
    younger than ``running_timeout`` (default ``INGEST_LOCK_TIMEOUT_SECONDS``,
    after which ``_run_ingestion`` treats a running row as stale).
    """
    if running_timeout is None:
        running_timeout = datetime.timedelta(seconds=settings.INGEST_LOCK_TIMEOUT_SECONDS)
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
        guard = attempt_guard(state.consecutive_failures)
        if state.last_attempt_at is not None and now - state.last_attempt_at < guard:
            continue
        if (
            state.latest_status == "running"
            and state.latest_started_at is not None
            and now - state.latest_started_at < running_timeout
        ):
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
    """Read run history (last success/attempt, consecutive failures, latest run)
    and table emptiness for the given sources."""
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

    # Failed runs started after the source's last completed run (all of them when
    # it never completed): the exponent of the retry backoff.
    last_completed = (
        select(IngestRun.source, func.max(IngestRun.started_at).label("started_at"))
        .where(IngestRun.status == "completed")
        .group_by(IngestRun.source)
        .subquery()
    )
    failure_rows = await db.execute(
        select(IngestRun.source, func.count())
        .select_from(IngestRun)
        .outerjoin(last_completed, last_completed.c.source == IngestRun.source)
        .where(IngestRun.status == "failed")
        .where(
            or_(
                last_completed.c.started_at.is_(None),
                IngestRun.started_at > last_completed.c.started_at,
            )
        )
        .group_by(IngestRun.source)
    )
    failures = dict(failure_rows.all())

    latest_rows = await db.execute(
        select(IngestRun.source, IngestRun.status, IngestRun.started_at)
        .distinct(IngestRun.source)
        .order_by(IngestRun.source, IngestRun.started_at.desc())
    )
    latest = {source: (status, started) for source, status, started in latest_rows.all()}

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
                consecutive_failures=failures.get(source, 0),
                latest_status=latest.get(source, (None, None))[0],
                latest_started_at=latest.get(source, (None, None))[1],
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
    ``recheck=False`` to force every source and keeps ``_run_ingestion``'s retry
    chain. Re-checked catch-up runs (``startup``/``catchup``) pass the maximum
    retry count so no retry is scheduled: the next catch-up, under the failure
    backoff, is the retry.

    Errors from the re-check or the ingestion are logged and the sequence
    continues with the next source.
    """
    from app.api.routes.v1.ingest import _run_ingestion

    kwargs: dict[str, str | int] = {"trigger": trigger}
    if recheck and trigger in _CATCHUP_TRIGGERS:
        kwargs["retry_count"] = settings.INGEST_MAX_RETRIES

    for src in sources:
        try:
            if recheck and not await _still_due(src):
                _log.info("Skipping %s catch-up — no longer due", src)
                continue
            _log.info("Starting %s ingestion...", src)
            await _run_ingestion(src, **kwargs)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            # _run_ingestion logs and persists its own errors; this also covers a
            # failed re-check. Continue rather than abort the whole sequence.
            _log.exception("Catch-up of %s failed (%s)", src, trigger)


async def run_forced_seed(sources: list[str]) -> None:
    """FORCE_SEED: ingest every source without re-checking, one catch-up at a time.

    Holds the same lock as ``run_catchup`` so a sweep cannot overlap it.
    """
    async with _catchup_lock:
        await run_sequential_ingest(sources, trigger="startup", recheck=False)


async def run_catchup(trigger: str) -> list[str]:
    """Select due sources and ingest them sequentially; return what was selected.

    Shared by process start (``"startup"``) and the hourly sweep (``"catchup"``).
    With INGEST_CATCHUP_ON_STARTUP=false only empty tables are seeded. Single
    flight: if another catch-up (or FORCE_SEED) is running, log and return ``[]``
    at once without waiting.
    """
    if _catchup_lock.locked():
        _log.info("Catch-up (%s) skipped — another catch-up is already running", trigger)
        return []
    async with _catchup_lock:
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
