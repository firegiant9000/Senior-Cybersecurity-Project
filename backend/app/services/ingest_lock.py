"""PostgreSQL advisory lock helpers for ingest run exclusion.

Each data source gets a deterministic int64 lock key derived from its name.
pg_try_advisory_lock is non-blocking — it returns False immediately if the
lock is already held rather than waiting.  Advisory locks are session-scoped:
they are automatically released when the database connection closes, so a
crashed process cannot leave a lock dangling indefinitely.

Stale-run protection (separate from locking):
    If a run has been in status="running" for longer than
    INGEST_LOCK_TIMEOUT_SECONDS we mark it failed before attempting a new
    acquire.  This handles the rare case where the DB connection was closed
    before the advisory lock was explicitly released.
"""

import datetime
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ingest_run import IngestRun

logger = logging.getLogger(__name__)

# Deterministic per-source lock keys (arbitrary stable int64 values).
_LOCK_KEYS: dict[str, int] = {
    "nvd": 0x696E6765_73744E56,  # "ingestNV"
    "cisa_kev": 0x696E6765_73744B45,  # "ingestKE"
    "ic3": 0x696E6765_73744943,  # "ingestIC"
    "economics": 0x696E6765_73744543,  # "ingestEC"
}


# Fallback: derive a key for any source not in the table above.
def _lock_key(source: str) -> int:
    key = _LOCK_KEYS.get(source)
    if key is not None:
        return key
    # Deterministic hash using sha256, folded into signed int64 range.
    # Python's built-in hash() is PYTHONHASHSEED-randomized per process, so
    # it cannot be used here — different app instances would derive different
    # lock keys for the same source, defeating cross-instance exclusion.
    import hashlib  # noqa: PLC0415

    digest = hashlib.sha256(source.encode()).digest()
    raw = int.from_bytes(digest[:8], "big")
    return raw % (2**63 - 1)  # fold into positive signed int64


async def expire_stale_runs(session: AsyncSession, source: str) -> None:
    """Mark timed-out running records as failed before we attempt a new lock.

    This is a defence-in-depth measure: advisory locks self-release on
    connection close, so a truly active lock should never be stale.  But if a
    row was left in status='running' (e.g. the process was SIGKILLed before it
    could update the row), we clean it up here.
    """
    timeout = settings.INGEST_LOCK_TIMEOUT_SECONDS
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=timeout)
    stmt = select(IngestRun).where(
        IngestRun.source == source,
        IngestRun.status == "running",
        IngestRun.started_at < cutoff,
    )
    result = await session.execute(stmt)
    stale_runs = result.scalars().all()
    for run in stale_runs:
        run.status = "failed"
        run.finished_at = datetime.datetime.utcnow()
        run.error_message = f"Timed out after {timeout}s — process likely crashed mid-run."
        logger.warning(
            "Marked stale ingest run as failed",
            extra={
                "source": source,
                "run_id": str(run.id),
                "started_at": run.started_at.isoformat(),
            },
        )
    if stale_runs:
        await session.commit()


async def try_acquire_lock(session: AsyncSession, source: str) -> bool:
    """Attempt to acquire a PG advisory lock for *source*.

    Returns True if the lock was acquired, False if already held by another
    session (i.e. a concurrent ingestion is running).
    """
    key = _lock_key(source)
    result = await session.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
    acquired: bool = result.scalar()  # type: ignore[assignment]
    if not acquired:
        logger.info(
            "Ingest lock already held — skipping run",
            extra={"source": source, "lock_key": key},
        )
    return acquired


async def release_lock(session: AsyncSession, source: str) -> None:
    """Release the PG advisory lock for *source*.

    Safe to call even if the lock is not held (pg_advisory_unlock returns
    False silently in that case).  We commit after the unlock to ensure the
    statement is flushed to the server before the session closes.
    """
    key = _lock_key(source)
    await session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    await session.commit()
