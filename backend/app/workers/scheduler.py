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


def init_scheduler() -> None:
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

    if not registered:
        logger.info("No ingest schedules configured — scheduler idle")
    else:
        logger.info("Scheduler jobs registered: %s", ", ".join(registered))
