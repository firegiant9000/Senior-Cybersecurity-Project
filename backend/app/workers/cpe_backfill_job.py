"""Background CPE-criteria backfill job (Month 3, Phase 1 tail).

``persist_cpe_configurations`` captures NVD version ranges inline as new CVEs
are ingested, but CVEs ingested *before* that landed have no ``cve_cpe_match``
rows — leaving the matcher blind to the pre-existing corpus. This job walks
those CVEs and backfills their criteria from NVD.

It is bounded (``NVD_CPE_BACKFILL_MAX_PER_RUN`` per run) and guarded by an
advisory lock so it never overlaps another backfill or doubles NVD load against
the nightly CVE ingest. The TTL skip inside ``backfill_cpe_configurations``
means successive runs converge and then no-op.

Two entry points mirror the matcher job: ``run_cpe_backfill_sweep`` (scheduled)
and the same callable used by the admin trigger route.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.db.engine import AsyncSessionLocal, engine
from app.ingestors.nvd_cpe import backfill_cpe_configurations
from app.services.ingest_lock import release_or_invalidate, try_acquire_lock

logger = logging.getLogger(__name__)

_LOCK_SOURCE = "cpe_backfill"


async def run_cpe_backfill_sweep(*, trigger: str = "scheduled") -> dict[str, int]:
    """Backfill CPE criteria for up to ``NVD_CPE_BACKFILL_MAX_PER_RUN`` CVEs.

    Returns the ``backfill_cpe_configurations`` result counts, or an empty dict
    if the lock was already held (another backfill is running — skip, not wait).
    """
    settings = get_settings()
    # Session-level advisory lock on a dedicated connection held for the whole
    # run; the ORM session's commits return its connection to the pool, so an
    # unlock issued through it could hit a different connection and leak the lock.
    async with engine.connect() as lock_conn, AsyncSessionLocal() as db:
        if not await try_acquire_lock(lock_conn, _LOCK_SOURCE):
            logger.info("CPE backfill lock held — skipping run", extra={"trigger": trigger})
            return {}
        try:
            result = await backfill_cpe_configurations(
                db, limit=settings.NVD_CPE_BACKFILL_MAX_PER_RUN
            )
            logger.info("CPE backfill complete", extra={"trigger": trigger, **result})
            return result
        except Exception:
            logger.exception("CPE backfill failed", extra={"trigger": trigger})
            raise
        finally:
            # Unlocks on the same connection, or invalidates it so the lock dies with it.
            await release_or_invalidate(lock_conn, _LOCK_SOURCE)


__all__ = ["run_cpe_backfill_sweep"]
