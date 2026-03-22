"""Ingest run tracking service."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_run import IngestRun

logger = logging.getLogger(__name__)


async def start_ingest_run(session: AsyncSession, source: str) -> IngestRun:
    """Create a new ingest run record with status 'running'."""
    run = IngestRun(
        source=source,
        status="running",
        started_at=datetime.now(UTC),
        records_ingested=0,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    logger.info("Started ingest run %s for source=%s", run.id, source)
    return run


async def finish_ingest_run(
    session: AsyncSession,
    run: IngestRun,
    *,
    status: str = "success",
    records: int = 0,
    error_message: str | None = None,
) -> IngestRun:
    """Mark an ingest run as finished."""
    run.finished_at = datetime.now(UTC)
    run.status = status
    run.records_ingested = records
    run.error_message = error_message
    await session.commit()
    await session.refresh(run)
    logger.info(
        "Finished ingest run %s: status=%s records=%d",
        run.id,
        status,
        records,
    )
    return run
