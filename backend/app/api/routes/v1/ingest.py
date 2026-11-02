"""Ingest status and trigger routes — v1."""

import asyncio
import datetime
import logging
from collections import defaultdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import settings
from app.core.dependencies import require_role
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal, engine, get_session
from app.db.models import CVE, KEV, IC3Incident
from app.db.user import User
from app.models.ingest_run import IngestRun
from app.services.ingest_catchup import hours_since, is_stale, stale_thresholds

logger = logging.getLogger(__name__)

router = APIRouter()

# Triggers whose runs are redundant when another run already holds the lock.
_CATCHUP_TRIGGERS = frozenset({"startup", "catchup"})


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SourceFreshness(BaseModel):
    """Freshness info for a single data source."""

    source: str
    last_run_at: str | None
    last_successful_run_at: str | None = None
    consecutive_failures: int = 0
    status: str | None
    records_ingested: int | None
    total_records: int | None = None
    error_message: str | None = None
    trigger: str | None = None
    retry_count: int = 0
    skipped_reason: str | None = None


class FreshnessResponse(BaseModel):
    """Data freshness response — latest run per source."""

    sources: list[SourceFreshness]


class IngestTriggerResponse(BaseModel):
    """Response returned when an ingestion is triggered."""

    source: str
    status: str
    message: str


class RetryRunResponse(BaseModel):
    """Response for a retry request."""

    source: str
    status: str
    message: str


class CancelRunResponse(BaseModel):
    """Response for a cancel request."""

    cancelled: bool
    warning: str | None = None


class SourceHealthItem(BaseModel):
    """Health status for a single data source."""

    stale: bool
    last_success_hours_ago: float | None = None
    consecutive_failures: int = 0


class HealthResponse(BaseModel):
    """Ingest health endpoint response."""

    healthy: bool
    sources: dict[str, SourceHealthItem]


# ---------------------------------------------------------------------------
# Background ingestion helpers
# ---------------------------------------------------------------------------


async def _dispatch_ingestor(source: str, db: "AsyncSession") -> int:
    """Run the source-specific ingestor and return the record count."""
    if source == "nvd":
        from app.ingestors.nvd import ingest_nvd

        return await ingest_nvd(db, max_results=20000)
    if source == "cisa_kev":
        from app.ingestors.cisa_kev import ingest_cisa_kev

        return await ingest_cisa_kev(db)
    if source == "ic3":
        from app.ingestors.ic3_real import ingest_ic3_real

        return await ingest_ic3_real(db, use_pdf=False)
    if source == "economics":
        from app.ingestors.econ import ingest_region_economics

        await ingest_region_economics(db)
        return -1
    if source == "epss":
        from app.ingestors.epss import ingest_epss

        return await ingest_epss(db)
    return 0


async def _record_next_scheduled(db: AsyncSession, run: IngestRun, source: str) -> IngestRun:
    """Best-effort: store the APScheduler next-run time on *run*.

    Returns the run to keep using.  On failure the session is rolled back (so
    the ingestor that follows gets a clean session) and the row is re-fetched,
    because rollback expires instances and async lazy-loads would raise.
    """
    run_id = run.id
    try:
        from app.workers.scheduler import scheduler

        job = scheduler.get_job(f"ingest_{source}")
        if job and job.next_run_time:
            # APScheduler gives a tz-aware datetime; the column is naive UTC.
            run.next_scheduled_at = job.next_run_time.astimezone(datetime.UTC).replace(tzinfo=None)
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not record next_scheduled_at",
            extra={"source": source, "run_id": str(run_id)},
            exc_info=True,
        )
        await db.rollback()
        refreshed = await db.get(IngestRun, run_id)
        if refreshed is not None:
            return refreshed
    return run


async def _mark_failed(db: AsyncSession, run_id: UUID, source: str, exc: Exception) -> None:
    """Record a failed run.

    The ingestor may have failed at the DB level, leaving the session needing
    a rollback, so roll back and re-fetch the row first.  Never raises, so the
    caller still schedules the retry.
    """
    try:
        await db.rollback()
        failed_run = await db.get(IngestRun, run_id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.error_message = str(exc)[:500]
            failed_run.finished_at = datetime.datetime.utcnow()
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Could not record ingestion failure",
            extra={"source": source, "run_id": str(run_id)},
        )


def _schedule_retry(source: str, trigger: str, retry_count: int) -> None:
    """Schedule an automatic retry with exponential back-off, if any remain."""
    if retry_count >= settings.INGEST_MAX_RETRIES:
        logger.error(
            "Ingestion exhausted retries",
            extra={"source": source, "max_retries": settings.INGEST_MAX_RETRIES},
        )
        return
    # Back-off: 30s for first retry, 120s for second.
    delay = 30 * (4**retry_count)
    next_retry_count = retry_count + 1
    logger.info(
        "Scheduling retry %d/%d in %ds",
        next_retry_count,
        settings.INGEST_MAX_RETRIES,
        delay,
        extra={"source": source},
    )

    async def _retry() -> None:
        await asyncio.sleep(delay)
        await _run_ingestion(source, trigger=trigger, retry_count=next_retry_count)

    asyncio.create_task(_retry())


async def _run_ingestion(
    source: str,
    trigger: str = "manual",
    retry_count: int = 0,
    *,
    schedule_retry: bool = True,
) -> None:
    """Run an ingestion job and record the result in ingest_runs.

    ``schedule_retry=False`` (catch-up) records a failure without scheduling the
    retry chain; ``retry_count`` stays the attempt number (0 for a first attempt)
    so ``/freshness`` and ``/runs`` show only retries that happened.

    Acquires a PostgreSQL advisory lock before running so that concurrent
    calls for the same source are safely skipped rather than racing.  The
    lock is session-level, so it is taken on a dedicated connection that is
    held for the whole run and released on that same connection; the ORM
    session's commits hand its connection back to the pool and must not be
    used for the lock.

    Pool usage: the session work that precedes the lock is committed first.  On
    the skip path the lock connection is released back to the pool before the
    session is used again.  On the acquired path two pooled connections are held
    by design (the lock connection for the whole run, plus the session's own);
    that is bounded (at most one extra connection per source, 5 sources) and not
    a deadlock.
    """
    from app.services.ingest_lock import expire_stale_runs, try_acquire_lock

    async with AsyncSessionLocal() as db:
        # Clean up any runs that timed out without updating their status, and
        # commit so the session gives its connection back before we take another.
        await expire_stale_runs(db, source)
        await db.commit()

        lock_conn = await engine.connect()
        try:
            acquired = await try_acquire_lock(lock_conn, source)
            if acquired:
                await _run_locked(
                    db, lock_conn, source, trigger, retry_count, schedule_retry=schedule_retry
                )
        finally:
            await lock_conn.close()

        if acquired:
            return

        if trigger in _CATCHUP_TRIGGERS:
            # Catch-up is redundant by design; a "skipped" row would count as a
            # failure in _compute_consecutive_failures, so don't record one.
            logger.warning(
                "Catch-up ingestion not started — lock held",
                extra={"source": source, "trigger": trigger},
            )
            return

        skipped_run = IngestRun(
            source=source,
            status="skipped",
            trigger=trigger,
            retry_count=retry_count,
            skipped_reason="Lock held by a concurrent run",
            started_at=datetime.datetime.utcnow(),
            finished_at=datetime.datetime.utcnow(),
            records_ingested=0,
        )
        db.add(skipped_run)
        await db.commit()
        logger.info(
            "Skipped ingestion — lock held",
            extra={"source": source, "trigger": trigger},
        )


async def _run_locked(
    db: AsyncSession,
    lock_conn: AsyncConnection,
    source: str,
    trigger: str,
    retry_count: int,
    *,
    schedule_retry: bool = True,
) -> None:
    """Run one ingestion while holding the advisory lock on *lock_conn*.

    Everything after the lock was acquired lives inside the ``try`` whose
    ``finally`` releases it, so no failure (run-row commit, scheduler lookup,
    rollback/re-fetch) can return the connection to the pool still locked.
    Once the running row exists, a failure before or during the ingestor marks
    it failed and follows the same retry rule: ``_schedule_retry``, unless
    ``schedule_retry`` is False (catch-up), which only logs.
    """
    from app.services.ingest_lock import release_or_invalidate

    try:
        run = IngestRun(
            source=source,
            status="running",
            trigger=trigger,
            retry_count=retry_count,
            started_at=datetime.datetime.utcnow(),
        )
        db.add(run)
        await db.commit()
        # A rollback expires ORM instances (and async lazy-loads raise), so keep
        # the id and re-fetch the row after any rollback.
        run_id = run.id

        _start = datetime.datetime.utcnow()
        # The running row is committed, so any failure from here on (including
        # the scheduler lookup's rollback/re-fetch) must mark it failed rather
        # than leave a phantom "running" row until expire_stale_runs.
        try:
            # [2B] Populate next_scheduled_at from APScheduler at run creation time.
            run = await _record_next_scheduled(db, run, source)

            count = await _dispatch_ingestor(source, db)

            elapsed = (datetime.datetime.utcnow() - _start).total_seconds()
            run.status = "completed"
            run.records_ingested = max(count, 0)
            run.finished_at = datetime.datetime.utcnow()
            await db.commit()
            logger.info(
                "Ingestion completed",
                extra={
                    "source": source,
                    "trigger": trigger,
                    "records": count,
                    "duration_s": round(elapsed, 2),
                    "run_id": str(run_id),
                },
            )

        except Exception as exc:
            elapsed = (datetime.datetime.utcnow() - _start).total_seconds()
            await _mark_failed(db, run_id, source, exc)
            logger.exception(
                "Ingestion failed",
                extra={
                    "source": source,
                    "trigger": trigger,
                    "duration_s": round(elapsed, 2),
                    "run_id": str(run_id),
                    "error": str(exc)[:200],
                    "retry_count": retry_count,
                },
            )
            if schedule_retry:
                _schedule_retry(source, trigger, retry_count)
            else:
                logger.info(
                    "Catch-up does not retry a failed run; the next catch-up is the retry",
                    extra={"source": source, "trigger": trigger},
                )
    finally:
        await release_or_invalidate(lock_conn, source)


def _compute_consecutive_failures(runs: list[IngestRun]) -> int:
    """Count consecutive terminal failures from most-recent backward."""
    count = 0
    for run in runs:
        if run.status in {"failed", "skipped"}:
            count += 1
        else:
            break
    return count


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def get_ingest_health(
    db: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Return ingest health status — no auth required (for external monitors).

    Reads from DB only, not APScheduler memory, so it is accurate on
    multi-instance deployments.
    """
    stmt = select(IngestRun).order_by(IngestRun.source, IngestRun.started_at.desc())
    result = await db.execute(stmt)
    all_runs = result.scalars().all()

    source_runs: dict[str, list[IngestRun]] = defaultdict(list)
    for run in all_runs:
        source_runs[run.source].append(run)

    now = datetime.datetime.utcnow()
    sources_health: dict[str, SourceHealthItem] = {}
    all_healthy = True

    for source, stale_hours in stale_thresholds().items():
        runs = source_runs.get(source, [])

        last_success = next((r for r in runs if r.status == "completed"), None)
        hours_ago = hours_since(last_success.finished_at if last_success else None, now)

        consec_fails = _compute_consecutive_failures(runs)
        stale = is_stale(hours_ago, stale_hours)

        if stale or consec_fails >= 2:
            all_healthy = False

        sources_health[source] = SourceHealthItem(
            stale=stale,
            last_success_hours_ago=round(hours_ago, 1) if hours_ago is not None else None,
            consecutive_failures=consec_fails,
        )

    return HealthResponse(healthy=all_healthy, sources=sources_health)


@router.get("/freshness", response_model=FreshnessResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ingest_freshness(
    request: Request,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("viewer")),
) -> FreshnessResponse:
    """Return the latest ingest run info for each data source."""
    try:
        stmt = select(IngestRun).order_by(IngestRun.source, IngestRun.started_at.desc())
        result = await db.execute(stmt)
        runs = result.scalars().all()

        # Group by source (already sorted descending by started_at within each group)
        source_groups: dict[str, list[IngestRun]] = defaultdict(list)
        for run in runs:
            source_groups[run.source].append(run)

        # Query total record counts per source table
        source_table_map = {
            "nvd": CVE,
            "cisa_kev": KEV,
            "ic3": IC3Incident,
        }
        total_counts: dict[str, int] = {}
        for src_name, model in source_table_map.items():
            count_result = await db.execute(select(func.count()).select_from(model))
            total_counts[src_name] = int(count_result.scalar_one())

        sources = []
        for source, group in source_groups.items():
            latest = group[0]

            # [2A] Last successful run
            last_success = next((r for r in group if r.status == "completed"), None)
            last_successful_run_at: str | None = None
            if last_success and last_success.finished_at:
                last_successful_run_at = last_success.finished_at.replace(
                    tzinfo=datetime.UTC
                ).isoformat()

            # [2A] Consecutive failures
            consec_fails = _compute_consecutive_failures(group)

            sources.append(
                SourceFreshness(
                    source=source,
                    last_run_at=(
                        (latest.finished_at or latest.started_at)
                        .replace(tzinfo=datetime.UTC)
                        .isoformat()
                        if (latest.finished_at or latest.started_at)
                        else None
                    ),
                    last_successful_run_at=last_successful_run_at,
                    consecutive_failures=consec_fails,
                    status=latest.status,
                    records_ingested=latest.records_ingested,
                    total_records=total_counts.get(source),
                    error_message=latest.error_message,
                    trigger=getattr(latest, "trigger", None),
                    retry_count=getattr(latest, "retry_count", 0),
                    skipped_reason=getattr(latest, "skipped_reason", None),
                )
            )
        return FreshnessResponse(sources=sources)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error fetching ingest freshness: %s", exc)
        return FreshnessResponse(sources=[])


class IngestRunItem(BaseModel):
    """Single ingest run record."""

    model_config = ConfigDict(from_attributes=True)

    id: str  # noqa: A003
    source: str
    started_at: str | None
    finished_at: str | None
    status: str
    records_ingested: int
    error_message: str | None = None
    trigger: str = "manual"
    retry_count: int = 0
    skipped_reason: str | None = None
    next_scheduled_at: str | None = None


class IngestRunsResponse(BaseModel):
    """Paginated ingest run history."""

    items: list[IngestRunItem]
    total: int
    page: int
    page_size: int


@router.get("/runs", response_model=IngestRunsResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ingest_runs(
    request: Request,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    source: Annotated[str | None, Query(description="Filter by source name")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("viewer")),
) -> IngestRunsResponse:
    """Return paginated historical ingest run records."""
    try:
        conditions = []
        if source:
            conditions.append(IngestRun.source == source)
        if status:
            conditions.append(IngestRun.status == status)

        base_stmt = select(IngestRun)
        count_stmt = select(func.count(IngestRun.id))
        for cond in conditions:
            base_stmt = base_stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar_one())

        stmt = (
            base_stmt.order_by(IngestRun.started_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await db.execute(stmt)
        runs = result.scalars().all()

        items = [
            IngestRunItem(
                id=str(run.id),
                source=run.source,
                started_at=run.started_at.replace(tzinfo=datetime.UTC).isoformat()
                if run.started_at
                else None,
                finished_at=run.finished_at.replace(tzinfo=datetime.UTC).isoformat()
                if run.finished_at
                else None,
                status=run.status,
                records_ingested=run.records_ingested,
                error_message=run.error_message,
                trigger=getattr(run, "trigger", "manual"),
                retry_count=getattr(run, "retry_count", 0),
                skipped_reason=getattr(run, "skipped_reason", None),
                next_scheduled_at=run.next_scheduled_at.replace(tzinfo=datetime.UTC).isoformat()
                if getattr(run, "next_scheduled_at", None)
                else None,
            )
            for run in runs
        ]
        return IngestRunsResponse(items=items, total=total, page=page, page_size=page_size)
    except Exception as exc:
        logger.exception("Error fetching ingest runs: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# [2C] Retry and cancel endpoints


@router.post("/runs/{run_id}/retry", response_model=RetryRunResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def retry_ingest_run(
    request: Request,  # noqa: ARG001
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("admin")),
) -> RetryRunResponse:
    """Retry a failed ingest run. Admin only."""
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    run = await db.get(IngestRun, run_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}'; only failed runs can be retried",
        )

    background_tasks.add_task(_run_ingestion, run.source, "manual")
    return RetryRunResponse(
        source=run.source,
        status="started",
        message=f"{run.source} ingestion started. Check GET /api/v1/ingest/freshness for status.",
    )


@router.post("/runs/{run_id}/cancel", response_model=CancelRunResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def cancel_ingest_run(
    request: Request,  # noqa: ARG001
    run_id: str,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("admin")),
) -> CancelRunResponse:
    """Cancel a running ingest run by marking it failed. Admin only.

    Note: this marks the DB record as failed but cannot stop the underlying
    asyncio.create_task — the task continues until it completes or errors.
    """
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    run = await db.get(IngestRun, run_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}'; only running runs can be cancelled",
        )

    run.status = "failed"
    run.error_message = "Manually cancelled"
    run.finished_at = datetime.datetime.utcnow()
    await db.commit()

    return CancelRunResponse(
        cancelled=True,
        warning=(
            "The database record has been marked as failed, but the underlying async task "
            "may still be running until it completes or errors naturally."
        ),
    )


class ScheduleJobInfo(BaseModel):
    """Info for a single scheduled ingest job."""

    source: str
    cron_expr: str
    next_fire_time: str | None
    enabled: bool


class ScheduleResponse(BaseModel):
    """Response for GET /schedule."""

    scheduler_enabled: bool
    jobs: list[ScheduleJobInfo]


@router.get("/schedule", response_model=ScheduleResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ingest_schedule(
    request: Request,  # noqa: ARG001
    _: User = Depends(require_role("viewer")),
) -> ScheduleResponse:
    """Return the current scheduler configuration and next fire times for each source."""
    from app.workers.scheduler import scheduler

    enabled = settings.SCHEDULER_ENABLED
    source_crons = {
        "nvd": settings.INGEST_SCHEDULE_NVD,
        "cisa_kev": settings.INGEST_SCHEDULE_KEV,
        "ic3": settings.INGEST_SCHEDULE_IC3,
        "economics": settings.INGEST_SCHEDULE_ECONOMICS,
        "epss": settings.INGEST_SCHEDULE_EPSS,
    }

    jobs: list[ScheduleJobInfo] = []
    for source, cron_expr in source_crons.items():
        job = scheduler.get_job(f"ingest_{source}") if enabled else None
        next_fire: str | None = None
        if job and job.next_run_time:
            next_fire = job.next_run_time.isoformat()
        jobs.append(
            ScheduleJobInfo(
                source=source,
                cron_expr=cron_expr or "(not scheduled)",
                next_fire_time=next_fire,
                enabled=bool(cron_expr and job is not None),
            )
        )

    return ScheduleResponse(scheduler_enabled=enabled, jobs=jobs)


@router.post("/trigger", response_model=list[IngestTriggerResponse])
@limiter.limit(settings.RATE_LIMIT_DATA)
async def trigger_ingestion(
    request: Request,
    background_tasks: BackgroundTasks,
    source: Literal["nvd", "cisa_kev", "ic3", "economics", "epss", "all"] = Query(
        default="all", description="Data source to ingest (or 'all')"
    ),
    _: User = Depends(require_role("admin")),
) -> list[IngestTriggerResponse]:
    """Trigger data ingestion for one or all sources.

    The ingestion runs in the background. Use GET /freshness to check status.
    """
    sources = ["nvd", "cisa_kev", "ic3", "economics", "epss"] if source == "all" else [source]

    results: list[IngestTriggerResponse] = []
    for src in sources:
        background_tasks.add_task(_run_ingestion, src, "manual")
        results.append(
            IngestTriggerResponse(
                source=src,
                status="started",
                message=f"{src} ingestion started in background. Check GET /api/v1/ingest/freshness for status.",
            )
        )

    return results


@router.post("/cpe-backfill", response_model=IngestTriggerResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def trigger_cpe_backfill(
    request: Request,  # noqa: ARG001
    _: User = Depends(require_role("admin")),
) -> IngestTriggerResponse:
    """Backfill CPE version-criteria for the pre-existing CVE corpus.

    Runs one bounded backfill pass (``NVD_CPE_BACKFILL_MAX_PER_RUN`` CVEs) in the
    background. Re-run until it reports no further CVEs to seed the matcher for
    the initial corpus; the nightly sweep handles steady state thereafter.
    """
    from app.workers.cpe_backfill_job import run_cpe_backfill_sweep

    asyncio.create_task(run_cpe_backfill_sweep(trigger="manual"))
    return IngestTriggerResponse(
        source="cpe_backfill",
        status="started",
        message=(
            "CPE backfill started in background (bounded per run). "
            "Re-run until persisted=0 for the initial corpus."
        ),
    )


# ---------------------------------------------------------------------------
# Normalization log — admin read endpoint
# ---------------------------------------------------------------------------


class NormalizationLogItem(BaseModel):
    id: int
    data_type: str
    raw_value: str
    normalized_value: str
    confidence: float
    method: str
    org_id: int | None = None
    created_at: str


class NormalizationLogResponse(BaseModel):
    items: list[NormalizationLogItem]
    total: int
    page: int
    page_size: int


@router.get("/normalization-log", response_model=NormalizationLogResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_normalization_log(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    data_type: Annotated[str | None, Query(description="Filter by data type")] = None,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("admin")),
) -> NormalizationLogResponse:
    """Return paginated normalization audit log (admin only)."""
    from sqlalchemy import desc

    from app.db.normalization_log import NormalizationLog

    conditions = []
    if data_type:
        conditions.append(NormalizationLog.data_type == data_type)

    total_result = await db.execute(
        select(func.count()).select_from(NormalizationLog).where(*conditions)
    )
    total = int(total_result.scalar_one())

    rows_result = await db.execute(
        select(NormalizationLog)
        .where(*conditions)
        .order_by(desc(NormalizationLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    items = [
        NormalizationLogItem(
            id=r.id,
            data_type=r.data_type,
            raw_value=r.raw_value,
            normalized_value=r.normalized_value,
            confidence=float(r.confidence),
            method=r.method,
            org_id=r.org_id,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return NormalizationLogResponse(items=items, total=total, page=page, page_size=page_size)
