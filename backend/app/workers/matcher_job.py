"""Background CPE-matching job (Month 3, Phase 4).

Runs the version-aware ``CpeMatcher`` over an org's inventory and persists the
results to ``asset_findings`` off the request path. Two entry points:

* ``run_matcher_for_org`` — match a single org, guarded by a per-org advisory
  lock so a scheduled sweep and an import-triggered run never race on the same
  org. It opens its own session, so it is safe to schedule as a FastAPI
  background task after the request's session has closed.
* ``run_matcher_sweep`` — the scheduled job: find every org whose inventory
  changed since its findings were last computed and match each one. This is the
  catch-all safety net for anything the inline triggers miss.

The CSV import and M365 sync schedule ``run_matcher_for_org`` directly; the
sweep backstops them. The matcher is recomputed at the org level (not per
scan_run) because a refreshed asset does not change its ``created_by_scan_run_id``
and would otherwise be skipped.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from app.db.asset_finding import AssetFinding
from app.db.engine import AsyncSessionLocal
from app.db.scan_run import ScanRun
from app.services.asset_findings_service import AssetFindingsService
from app.services.ingest_lock import release_lock, try_acquire_lock

logger = logging.getLogger(__name__)

# Strong references to in-flight fire-and-forget matcher tasks. The event loop
# only holds a *weak* reference to a bare ``create_task`` result, so without this
# an import-triggered matcher run could be garbage-collected mid-flight. Tasks
# discard themselves on completion.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def trigger_matcher_async(org_id: int, *, trigger: str) -> asyncio.Task:
    """Fire ``run_matcher_for_org`` off the request path, keeping a strong ref.

    Used by the CSV-import and M365-sync handlers so the new inventory
    auto-populates findings without the task being collected before it runs.
    """
    task = asyncio.create_task(run_matcher_for_org(org_id, trigger=trigger))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


def _lock_source(org_id: int) -> str:
    """Per-org advisory-lock key fed to ``try_acquire_lock``.

    ``ingest_lock._lock_key`` hashes unknown source strings into a stable int64,
    so each org serializes independently without colliding with the ingestor
    locks.
    """
    return f"matcher_org_{org_id}"


async def run_matcher_for_org(org_id: int, *, trigger: str = "manual") -> int:
    """Recompute + persist findings for every asset in one org.

    Returns the number of assets processed, or 0 if the org's matcher lock was
    already held by a concurrent run (which is then skipped, not awaited).
    """
    source = _lock_source(org_id)
    async with AsyncSessionLocal() as db:
        if not await try_acquire_lock(db, source):
            logger.info(
                "Matcher lock held — skipping org",
                extra={"org_id": org_id, "trigger": trigger},
            )
            return 0
        try:
            count = await AssetFindingsService(db).compute_and_persist_for_org(org_id)
            logger.info(
                "Matcher run complete",
                extra={"org_id": org_id, "assets": count, "trigger": trigger},
            )
            return count
        except Exception:
            logger.exception(
                "Matcher run failed",
                extra={"org_id": org_id, "trigger": trigger},
            )
            raise
        finally:
            try:
                await release_lock(db, source)
            except Exception:  # noqa: BLE001
                # Session may be broken after a failure; the advisory lock
                # self-releases when the connection closes.
                logger.debug(
                    "matcher release_lock failed — lock will self-release on close",
                    extra={"org_id": org_id},
                )


async def _orgs_needing_match() -> list[int]:
    """Org ids whose latest successful scan_run is newer than their findings.

    An org with successful scan_runs but zero findings (the left-join NULL case)
    always qualifies, so a first-ever import is picked up by the sweep.
    """
    last_scan = (
        select(ScanRun.org_id, func.max(ScanRun.started_at).label("last_scan"))
        .where(ScanRun.status == "succeeded")
        .group_by(ScanRun.org_id)
        .subquery()
    )
    last_finding = (
        select(
            AssetFinding.org_id,
            func.max(AssetFinding.updated_at).label("last_finding"),
        )
        .group_by(AssetFinding.org_id)
        .subquery()
    )
    stmt = (
        select(last_scan.c.org_id)
        .select_from(last_scan.outerjoin(last_finding, last_scan.c.org_id == last_finding.c.org_id))
        .where(
            (last_finding.c.last_finding.is_(None))
            | (last_scan.c.last_scan > last_finding.c.last_finding)
        )
    )
    async with AsyncSessionLocal() as db:
        return list((await db.execute(stmt)).scalars().all())


async def run_matcher_sweep() -> None:
    """Scheduled entry point: match every org with inventory newer than findings."""
    org_ids = await _orgs_needing_match()
    if not org_ids:
        logger.info("Matcher sweep: no orgs need recompute")
        return
    logger.info("Matcher sweep: %d org(s) need recompute", len(org_ids))
    for org_id in org_ids:
        try:
            await run_matcher_for_org(org_id, trigger="scheduled")
        except Exception:  # noqa: BLE001
            # Already logged inside run_matcher_for_org; keep sweeping the rest.
            logger.debug("Matcher sweep continuing past org %s failure", org_id)


__all__ = ["run_matcher_for_org", "run_matcher_sweep", "trigger_matcher_async"]
