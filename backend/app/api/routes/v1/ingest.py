"""Ingest status and trigger routes — v1."""

import asyncio
import datetime
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import require_role
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal, get_session
from app.db.models import CVE, KEV, IC3Incident
from app.db.user import User
from app.models.ingest_run import IngestRun

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SourceFreshness(BaseModel):
    """Freshness info for a single data source."""

    source: str
    last_run_at: str | None  # ISO datetime string
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


# ---------------------------------------------------------------------------
# Background ingestion helpers
# ---------------------------------------------------------------------------


async def _run_ingestion(
    source: str,
    trigger: str = "manual",
    retry_count: int = 0,
) -> None:
    """Run an ingestion job and record the result in ingest_runs.

    Acquires a PostgreSQL advisory lock before running so that concurrent
    calls for the same source are safely skipped rather than racing.
    """
    from app.services.ingest_lock import expire_stale_runs, release_lock, try_acquire_lock

    async with AsyncSessionLocal() as db:
        # Clean up any runs that timed out without updating their status.
        await expire_stale_runs(db, source)

        # Attempt non-blocking advisory lock.
        if not await try_acquire_lock(db, source):
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
            return

        run = IngestRun(
            source=source,
            status="running",
            trigger=trigger,
            retry_count=retry_count,
            started_at=datetime.datetime.utcnow(),
        )
        db.add(run)
        await db.commit()

        _start = datetime.datetime.utcnow()
        try:
            count = 0
            if source == "nvd":
                from app.ingestors.nvd import ingest_nvd

                count = await ingest_nvd(db, max_results=20000)
            elif source == "cisa_kev":
                from app.ingestors.cisa_kev import ingest_cisa_kev

                count = await ingest_cisa_kev(db)
            elif source == "ic3":
                from app.ingestors.ic3_real import ingest_ic3_real

                count = await ingest_ic3_real(db, use_pdf=False)
            elif source == "economics":
                from app.ingestors.econ import ingest_region_economics

                await ingest_region_economics(db)
                count = -1

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
                    "run_id": str(run.id),
                },
            )

        except Exception as exc:
            elapsed = (datetime.datetime.utcnow() - _start).total_seconds()
            run.status = "failed"
            run.error_message = str(exc)[:500]
            run.finished_at = datetime.datetime.utcnow()
            await db.commit()
            logger.exception(
                "Ingestion failed",
                extra={
                    "source": source,
                    "trigger": trigger,
                    "duration_s": round(elapsed, 2),
                    "run_id": str(run.id),
                    "error": str(exc)[:200],
                    "retry_count": retry_count,
                },
            )
            # Schedule automatic retry with exponential back-off unless we've
            # exhausted retries or this was already a retry run.
            if retry_count < settings.INGEST_MAX_RETRIES:
                # Back-off: 30s for first retry, 120s for second.
                delay = 30 * (4**retry_count)  # 30s, 120s
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
            else:
                logger.error(
                    "Ingestion exhausted retries",
                    extra={"source": source, "max_retries": settings.INGEST_MAX_RETRIES},
                )

        finally:
            try:
                await release_lock(db, source)
            except Exception:  # noqa: BLE001
                # Session may be broken after a DB-level failure; advisory lock
                # self-releases when the session closes, so this is safe to swallow.
                logger.debug(
                    "release_lock failed — lock will self-release on session close",
                    extra={"source": source},
                )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/freshness", response_model=FreshnessResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ingest_freshness(
    request: Request,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("viewer")),
) -> FreshnessResponse:
    """Return the latest ingest run info for each data source."""
    try:
        # Fetch all runs ordered by source + started_at desc, then deduplicate in Python
        stmt = select(IngestRun).order_by(IngestRun.source, IngestRun.started_at.desc())
        result = await db.execute(stmt)
        runs = result.scalars().all()

        # Keep only the most recent run per source
        seen: set[str] = set()
        latest: list[IngestRun] = []
        for run in runs:
            if run.source not in seen:
                seen.add(run.source)
                latest.append(run)

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

        sources = [
            SourceFreshness(
                source=run.source,
                last_run_at=(
                    run.finished_at.replace(tzinfo=datetime.UTC).isoformat()
                    if run.finished_at
                    else None
                ),
                status=run.status,
                records_ingested=run.records_ingested,
                total_records=total_counts.get(run.source),
                error_message=run.error_message,
                trigger=getattr(run, "trigger", None),
                retry_count=getattr(run, "retry_count", 0),
                skipped_reason=getattr(run, "skipped_reason", None),
            )
            for run in latest
        ]
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
    _request: Request,
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
    source: Literal["nvd", "cisa_kev", "ic3", "economics", "all"] = Query(
        default="all", description="Data source to ingest (or 'all')"
    ),
    _: User = Depends(require_role("admin")),
) -> list[IngestTriggerResponse]:
    """Trigger data ingestion for one or all sources.

    The ingestion runs in the background. Use GET /freshness to check status.
    """
    sources = ["nvd", "cisa_kev", "ic3", "economics"] if source == "all" else [source]

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
