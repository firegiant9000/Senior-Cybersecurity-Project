"""Audit helpers for ingestion workflows (IngestRun).

This module provides lightweight helpers to create/update ``ingest_runs`` records
so ingestion activity is auditable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_run import IngestRun


async def start_ingest_run(db: AsyncSession, *, source: str) -> IngestRun:
    """Create and persist an ingest run with status ``Running``."""
    run = IngestRun(source=source, status="Running")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def finish_ingest_run(
    db: AsyncSession,
    run: IngestRun,
    *,
    status: str,
    records_ingested: int = 0,
    error_message: str | None = None,
) -> IngestRun:
    """Finalize an ingest run with success/failure fields and persist it."""
    run.status = status
    run.finished_at = datetime.utcnow()
    run.records_ingested = max(int(records_ingested), 0)
    run.error_message = error_message
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run

