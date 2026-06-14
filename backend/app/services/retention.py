"""Retention policy service.

Per Month 1 Phase C2 the policy was *documented* but not enforced; Month 4
Phase 7 wires the cron-driven sweep that actually prunes. This module is the
single seam the scheduler (``workers/scheduler.py``) and the manual
``POST /organizations/{id}/retention/run`` route both call.

Current policy (2026-06):

* **Scan history**: retained primarily by **age** — runs older than
  ``scan_run_retention_days`` are deleted — with a per-org **safety ceiling**
  (``max_scan_runs_per_org``) that drops the oldest runs once an org exceeds it.
  This replaced an earlier "latest 12 scan_runs per org" rule that was far too
  aggressive for a scanner product: each agent host uploads one ``scan_run`` per
  scan, so a multi-host org blew past 12 in under a day and lost the history the
  month-over-month report depends on. ``scan_runs`` is org-scoped, not
  asset-scoped (the only asset↔scan link is ``assets.created_by_scan_run_id``,
  ``ON DELETE SET NULL``), so retention is enforced per org; deleting a pruned
  run only nulls that pointer on the few assets it created — assets, software,
  and findings are untouched.
* **Audit log**: rows are retained for 365 days from ``created_at`` and then
  deleted. Org deletion does **not** drop the row — the FK is
  ``ON DELETE SET NULL`` so historical actor/action data survives org removal
  with org-linkage cleared. This matches ``docs/pii_inventory.md``.
* **Agent scan nonces**: replay markers older than the replay window
  (``AGENT_SCAN_REPLAY_WINDOW_HOURS``) can never cause a rejection again, so they
  are purged to keep ``agent_scan_nonces`` bounded. Swept only on the global cron
  run, not the per-org manual hook.
* **Org export bundles**: never persisted server-side; streamed once and the
  bytes are discarded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select

from app.core.config import settings
from app.db.audit_log import AuditLog
from app.db.engine import AsyncSessionLocal
from app.db.scan_run import ScanRun
from app.repositories.agent_scan_nonces import SqlAgentScanNonceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPolicy:
    """Declarative retention thresholds; consumed by the sweep job."""

    scan_run_retention_days: int = 400
    max_scan_runs_per_org: int = 2000
    audit_log_retention_days: int = 365
    scan_nonce_retention_hours: int = 24


def get_policy() -> RetentionPolicy:
    """Return the active retention policy, sourced from settings (env-tunable)."""
    return RetentionPolicy(
        scan_run_retention_days=settings.SCAN_RUN_RETENTION_DAYS,
        max_scan_runs_per_org=settings.MAX_SCAN_RUNS_PER_ORG,
        scan_nonce_retention_hours=settings.AGENT_SCAN_REPLAY_WINDOW_HOURS,
    )


async def _prune_scan_runs(db, policy: RetentionPolicy, org_id: int | None) -> int:
    """Delete scan_runs past the time window OR beyond the per-org safety ceiling.

    A run is pruned if it is older than ``scan_run_retention_days`` (the primary
    policy) or ranks beyond ``max_scan_runs_per_org`` newest for its org (the
    backstop against unbounded growth). When ``org_id`` is given the prune is
    confined to that org (the manual dry-run route); otherwise every org is swept.
    """
    cutoff = datetime.now(UTC) - timedelta(days=policy.scan_run_retention_days)
    ranked = select(
        ScanRun.id,
        ScanRun.started_at,
        func.row_number()
        .over(partition_by=ScanRun.org_id, order_by=ScanRun.started_at.desc())
        .label("rn"),
    )
    if org_id is not None:
        ranked = ranked.where(ScanRun.org_id == org_id)
    ranked_sq = ranked.subquery()

    stale_ids = select(ranked_sq.c.id).where(
        or_(
            ranked_sq.c.started_at < cutoff,
            ranked_sq.c.rn > policy.max_scan_runs_per_org,
        )
    )
    result = await db.execute(
        delete(ScanRun)
        .where(ScanRun.id.in_(stale_ids))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


async def _prune_scan_nonces(db, policy: RetentionPolicy) -> int:
    """Purge replay nonces older than the replay window (closes the unbounded
    growth of ``agent_scan_nonces``). Global only — see ``run_retention_sweep``."""
    cutoff = datetime.now(UTC) - timedelta(hours=policy.scan_nonce_retention_hours)
    return await SqlAgentScanNonceRepository(db).purge_before(cutoff)


async def _prune_audit_log(db, policy: RetentionPolicy, org_id: int | None) -> int:
    """Delete audit_log rows older than the retention window."""
    cutoff = datetime.now(UTC) - timedelta(days=policy.audit_log_retention_days)
    stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
    if org_id is not None:
        stmt = stmt.where(AuditLog.org_id == org_id)
    result = await db.execute(stmt.execution_options(synchronize_session=False))
    return result.rowcount or 0


async def run_retention_sweep(org_id: int | None = None) -> dict[str, int]:
    """Prune scan history and audit log per the active policy.

    Opens its own session so it is safe to schedule (the request session is long
    gone by the time the cron fires) and to call from the manual route. Returns
    per-table delete counts. ``org_id=None`` sweeps every org; a value confines
    the sweep to one org for the admin dry-run endpoint.
    """
    policy = get_policy()
    async with AsyncSessionLocal() as db:
        scan_runs_deleted = await _prune_scan_runs(db, policy, org_id)
        audit_log_deleted = await _prune_audit_log(db, policy, org_id)
        # Nonces are global (the replay window is org-agnostic); purging them on
        # the per-org manual hook would reach outside the requested org, so only
        # the global cron path sweeps them.
        scan_nonces_deleted = 0 if org_id is not None else await _prune_scan_nonces(db, policy)
        await db.commit()

    counts = {
        "scan_runs": scan_runs_deleted,
        "audit_log": audit_log_deleted,
        "scan_nonces": scan_nonces_deleted,
    }
    logger.info("Retention sweep complete", extra={"org_id": org_id, **counts})
    return counts
