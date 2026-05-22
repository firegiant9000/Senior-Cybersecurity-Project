"""Retention policy service stub.

Per Month 1 Phase C2 of the execution plan, the policy is *documented* now
but not yet enforced by a scheduler — the cron-driven sweep lands in
Month 4. This module is the single seam where any future scheduled job
will hang itself, so callers (and ``data_lifecycle`` audit-log entries)
already have a stable name to reference.

Current policy (2026-05):

* **Scan history**: retain the latest 12 scans per asset; older runs are
  candidates for deletion.
* **Audit log**: rows are retained for 12 months from ``created_at`` and
  then deleted by the Month 4 sweep. Org deletion does **not** drop the
  row — the FK is ``ON DELETE SET NULL`` so historical actor/action data
  survives org removal for compliance, with org-linkage cleared. This
  matches the policy documented in ``docs/pii_inventory.md``.
* **Org export bundles**: never persisted server-side; streamed once and
  the bytes are discarded.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """Declarative retention thresholds; consumed by the (future) sweep job."""

    scans_per_asset: int = 12
    audit_log_retention_days: int = 365


DEFAULT_POLICY = RetentionPolicy()


def get_policy() -> RetentionPolicy:
    """Return the active retention policy. Hard-coded until Month 4."""
    return DEFAULT_POLICY


async def run_retention_sweep() -> dict[str, int]:
    """Placeholder for the Month 4 cron job; currently a no-op.

    Returns the per-table delete counts so the eventual scheduler can log
    them. Keeping the signature stable now means the cron wiring is a
    one-line change later.
    """
    return {}
