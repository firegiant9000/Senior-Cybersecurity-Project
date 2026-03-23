"""Helper functions for recording ingest run lifecycle in the database."""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_run import IngestRun


async def start_ingest_run(session: AsyncSession, *, source: str) -> IngestRun:
    """Create and persist a new ingest run record with status 'running'."""
    run = IngestRun(
        source=source,
        status="running",
        started_at=datetime.datetime.utcnow(),
    )
    session.add(run)
    await session.commit()
    return run


async def finish_ingest_run(
    session: AsyncSession,
    run: IngestRun,
    *,
    status: str,
    records_ingested: int = 0,
    error_message: str | None = None,
) -> None:
    """Update an ingest run record with final status and finish time."""
    run.status = status
    run.records_ingested = records_ingested
    run.finished_at = datetime.datetime.utcnow()
    if error_message is not None:
        run.error_message = error_message
    await session.commit()
