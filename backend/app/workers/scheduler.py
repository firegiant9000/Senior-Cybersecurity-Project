"""APScheduler-based background scheduler for periodic data ingestion.

Jobs are registered at startup for any source that has a cron expression
configured via environment variables (INGEST_SCHEDULE_NVD, etc.).  Empty
expressions mean the source is not scheduled.

The scheduler is in-process (AsyncIOScheduler) and shares the uvicorn event
loop.  Advisory locks in _run_ingestion prevent duplicate execution if the
app is ever scaled to multiple instances.

Set SCHEDULER_ENABLED=false to disable the scheduler entirely — useful when
running multiple Render instances where only one should fire scheduled jobs.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level scheduler instance — started/stopped in app lifespan.
scheduler = AsyncIOScheduler(timezone="UTC")

# Mapping from source name to its schedule config key.
_SOURCE_SCHEDULE_MAP: dict[str, str] = {
    "nvd": settings.INGEST_SCHEDULE_NVD,
    "cisa_kev": settings.INGEST_SCHEDULE_KEV,
    "ic3": settings.INGEST_SCHEDULE_IC3,
    "economics": settings.INGEST_SCHEDULE_ECONOMICS,
    "epss": settings.INGEST_SCHEDULE_EPSS,
}


async def _scheduled_ingest(source: str) -> None:
    """Coroutine executed by the scheduler for a given source.

    Delegates to _run_ingestion which handles locking, status tracking, and
    retry logic.  Exceptions are caught here so APScheduler doesn't suppress
    or retry the job on its own.
    """
    from app.api.routes.v1.ingest import _run_ingestion

    logger.info("Scheduled ingest firing", extra={"source": source})
    try:
        await _run_ingestion(source, trigger="scheduled")
    except Exception as exc:  # noqa: BLE001
        # Already logged inside _run_ingestion; swallow here so APScheduler
        # does not mark the job as permanently failed.
        logger.debug("Scheduled ingest exception swallowed by scheduler wrapper: %s", exc)


def init_scheduler() -> None:  # noqa: C901 — flat per-source registration loop
    """Register a scheduled job for each source with a configured cron expression.

    Called once during app startup.  Does nothing if SCHEDULER_ENABLED=false.
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("SCHEDULER_ENABLED=false — skipping scheduler init")
        return

    registered: list[str] = []
    for source, cron_expr in _SOURCE_SCHEDULE_MAP.items():
        if not cron_expr:
            continue
        try:
            trigger = CronTrigger.from_crontab(cron_expr, timezone="UTC")
        except ValueError as exc:
            logger.error(
                "Invalid cron expression for %s (%r): %s — job not scheduled",
                source,
                cron_expr,
                exc,
            )
            continue

        scheduler.add_job(
            _scheduled_ingest,
            trigger=trigger,
            args=[source],
            id=f"ingest_{source}",
            replace_existing=True,
            # Allow up to 5 minutes of latency before a misfired job is skipped.
            misfire_grace_time=300,
            coalesce=True,  # If multiple firings were missed, run only once.
        )
        registered.append(f"{source} ({cron_expr})")
        logger.info("Scheduled ingest job registered: %s @ %s", source, cron_expr)

    # Month 3 Phase 4: background CPE-matcher sweep (separate job function from
    # the ingestors, so it is registered outside the source loop).
    matcher_cron = settings.MATCHER_SCHEDULE
    if matcher_cron:
        try:
            matcher_trigger = CronTrigger.from_crontab(matcher_cron, timezone="UTC")
        except (ValueError, TypeError) as exc:
            logger.error(
                "Invalid MATCHER_SCHEDULE cron (%r): %s — matcher sweep not scheduled",
                matcher_cron,
                exc,
            )
        else:
            from app.workers.matcher_job import run_matcher_sweep

            scheduler.add_job(
                run_matcher_sweep,
                trigger=matcher_trigger,
                id="matcher_sweep",
                replace_existing=True,
                misfire_grace_time=300,
                coalesce=True,
            )
            registered.append(f"matcher_sweep ({matcher_cron})")
            logger.info("Scheduled matcher sweep registered @ %s", matcher_cron)

    # Month 3 Phase 1 tail: scheduled CPE-criteria backfill for the pre-existing
    # CVE corpus. Bounded per run and TTL-skipping, so it converges then no-ops.
    backfill_cron = settings.NVD_CPE_BACKFILL_SCHEDULE
    if backfill_cron:
        try:
            backfill_trigger = CronTrigger.from_crontab(backfill_cron, timezone="UTC")
        except (ValueError, TypeError) as exc:
            logger.error(
                "Invalid NVD_CPE_BACKFILL_SCHEDULE cron (%r): %s — backfill not scheduled",
                backfill_cron,
                exc,
            )
        else:
            from app.workers.cpe_backfill_job import run_cpe_backfill_sweep

            scheduler.add_job(
                run_cpe_backfill_sweep,
                trigger=backfill_trigger,
                id="cpe_backfill",
                replace_existing=True,
                misfire_grace_time=300,
                coalesce=True,
            )
            registered.append(f"cpe_backfill ({backfill_cron})")
            logger.info("Scheduled CPE backfill registered @ %s", backfill_cron)

    # Month 4 Phase 7: retention sweep (prune scan history + age out audit log).
    # Separate job function from the ingestors; runs after the matcher sweep so it
    # never prunes a scan_run mid-recompute.
    retention_cron = settings.RETENTION_SWEEP_SCHEDULE
    if retention_cron:
        try:
            retention_trigger = CronTrigger.from_crontab(retention_cron, timezone="UTC")
        except (ValueError, TypeError) as exc:
            logger.error(
                "Invalid RETENTION_SWEEP_SCHEDULE cron (%r): %s — retention sweep not scheduled",
                retention_cron,
                exc,
            )
        else:
            from app.services.retention import run_retention_sweep

            scheduler.add_job(
                run_retention_sweep,
                trigger=retention_trigger,
                id="retention_sweep",
                replace_existing=True,
                misfire_grace_time=300,
                coalesce=True,
            )
            registered.append(f"retention_sweep ({retention_cron})")
            logger.info("Scheduled retention sweep registered @ %s", retention_cron)

    if not registered:
        logger.info("No ingest schedules configured — scheduler idle")
    else:
        logger.info("Scheduler jobs registered: %s", ", ".join(registered))
