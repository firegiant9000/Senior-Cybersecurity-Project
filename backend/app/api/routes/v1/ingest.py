"""Ingest status and trigger routes — v1."""

import datetime
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal, get_session
from app.db.models import CVE, KEV, IC3Incident
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


async def _run_ingestion(source: str, **kwargs: object) -> None:
    """Run an ingestion job and record the result in ingest_runs."""
    run = IngestRun(source=source, status="running", started_at=datetime.datetime.utcnow())

    async with AsyncSessionLocal() as db:
        db.add(run)
        await db.commit()

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

            run.status = "completed"
            run.records_ingested = max(count, 0)
            run.finished_at = datetime.datetime.utcnow()
            await db.commit()
            logger.info("Ingestion %s completed: %s records", source, count)

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)[:500]
            run.finished_at = datetime.datetime.utcnow()
            await db.commit()
            logger.exception("Ingestion %s failed: %s", source, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/freshness", response_model=FreshnessResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ingest_freshness(
    request: Request,
    db: AsyncSession = Depends(get_session),
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
            )
            for run in runs
        ]
        return IngestRunsResponse(items=items, total=total, page=page, page_size=page_size)
    except Exception as exc:
        logger.exception("Error fetching ingest runs: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/trigger", response_model=list[IngestTriggerResponse])
@limiter.limit(settings.RATE_LIMIT_DATA)
async def trigger_ingestion(
    request: Request,
    background_tasks: BackgroundTasks,
    source: Literal["nvd", "cisa_kev", "ic3", "economics", "all"] = Query(
        default="all", description="Data source to ingest (or 'all')"
    ),
) -> list[IngestTriggerResponse]:
    """Trigger data ingestion for one or all sources.

    The ingestion runs in the background. Use GET /freshness to check status.
    """
    sources = ["nvd", "cisa_kev", "ic3", "economics"] if source == "all" else [source]

    results: list[IngestTriggerResponse] = []
    for src in sources:
        background_tasks.add_task(_run_ingestion, src)
        results.append(
            IngestTriggerResponse(
                source=src,
                status="started",
                message=f"{src} ingestion started in background. Check GET /api/v1/ingest/freshness for status.",
            )
        )

    return results
