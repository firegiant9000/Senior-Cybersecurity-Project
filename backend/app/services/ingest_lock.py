"""PostgreSQL advisory lock helpers for ingest run exclusion.

Each data source gets a deterministic int64 lock key derived from its name.
pg_try_advisory_lock is non-blocking — it returns False immediately if the
lock is already held rather than waiting.  Advisory locks are scoped to the
physical database connection (session-level): they survive COMMIT and are
released only by pg_advisory_unlock or when the connection closes, so a
crashed process cannot leave a lock dangling indefinitely.  A connection
returned to the SQLAlchemy pool is only ROLLBACKed, which does NOT release
advisory locks, so callers must acquire and release on one dedicated
``AsyncConnection`` held for the whole run, and ``invalidate()`` it if the
release fails.

Stale-run protection (separate from locking):
    If a run has been in status="running" for longer than
    INGEST_LOCK_TIMEOUT_SECONDS we mark it failed before attempting a new
    acquire.  This handles the rare case where the DB connection was closed
    before the advisory lock was explicitly released.
"""

import datetime
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

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


async def try_acquire_lock(conn: AsyncConnection | AsyncSession, source: str) -> bool:
    """Attempt to acquire a PG advisory lock for *source*.

    Returns True if the lock was acquired, False if already held by another
    session (i.e. a concurrent ingestion is running).

    Pass a dedicated ``AsyncConnection`` that the caller holds for the whole
    run and also hands to ``release_lock``.  On a connection the statement is
    committed so no transaction stays open; the session-level lock survives
    the commit.  (Passing an ORM session works but is unsafe under a pool:
    its commit returns the connection to the pool.)
    """
    key = _lock_key(source)
    result = await conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
    acquired: bool = result.scalar()  # type: ignore[assignment]
    await conn.commit()
    if not acquired:
        logger.info(
            "Ingest lock already held — skipping run",
            extra={"source": source, "lock_key": key},
        )
    return acquired


async def release_lock(conn: AsyncConnection | AsyncSession, source: str) -> None:
    """Release the PG advisory lock for *source*.

    Must run on the *same* connection that acquired the lock, otherwise
    pg_advisory_unlock silently returns False and the lock leaks.  Safe to
    call when the lock is not held.  Commits so no transaction is left open.
    Callers should ``invalidate()`` the connection if this raises.
    """
    key = _lock_key(source)
    await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    await conn.commit()


async def release_or_invalidate(lock_conn: AsyncConnection, source: str) -> None:
    """Release the advisory lock on its own connection, or kill that connection.

    The lock is bound to this physical connection, and a pooled connection is
    only ROLLBACKed on return, which does not release advisory locks.  If the
    unlock fails, invalidate so the connection is closed (releasing the lock)
    instead of being returned to the pool still locked.
    """
    try:
        await release_lock(lock_conn, source)
    except Exception:  # noqa: BLE001
        logger.warning(
            "release_lock failed — invalidating lock connection to free the lock",
            extra={"source": source},
            exc_info=True,
        )
        try:
            await lock_conn.invalidate()
        except Exception:  # noqa: BLE001
            logger.exception("Could not invalidate lock connection", extra={"source": source})
