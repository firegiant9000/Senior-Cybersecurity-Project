"""Ingest status routes — v1."""

import logging
import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.models.ingest_run import IngestRun

logger = logging.getLogger(__name__)

router = APIRouter()


class SourceFreshness(BaseModel):
    """Freshness info for a single data source."""

    source: str
    last_run_at: str | None  # ISO datetime string
    status: str | None
    records_ingested: int | None


class FreshnessResponse(BaseModel):
    """Data freshness response — latest run per source."""

    sources: list[SourceFreshness]


@router.get("/freshness", response_model=FreshnessResponse)
async def get_ingest_freshness(
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
            )
            for run in latest
        ]
        return FreshnessResponse(sources=sources)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error fetching ingest freshness: %s", exc)
        return FreshnessResponse(sources=[])
