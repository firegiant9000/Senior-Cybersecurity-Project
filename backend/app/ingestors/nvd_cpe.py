# app/ingestors/nvd_cpe.py
"""Parse and persist NVD CPE configurations (per-CVE affected version ranges).

NVD publishes the affected-version ranges for each CVE inside ``configurations``
(``versionStartIncluding`` / ``versionEndExcluding`` / etc.). The CVE ingestor
discarded everything but vendor/product; this module captures the full criteria
into ``cve_cpe_match`` so the Month 3 matcher can do version-aware matching.

``parse_cpe_configurations`` is a pure function (unit-testable, no DB). The
backfill function reuses the rate-limit-aware ``fetch_nvd_cve_by_id`` from
``app.ingestors.nvd``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.cve_cpe_match import CveCpeMatch
from app.db.models import CVE
from app.ingestors.nvd import fetch_nvd_cve_by_id

logger = logging.getLogger(__name__)


class CpeCriterion(TypedDict):
    """One parsed CPE match entry from an NVD CVE's configurations."""

    cpe_uri: str
    vendor: str | None
    product: str | None
    version_start_including: str | None
    version_start_excluding: str | None
    version_end_including: str | None
    version_end_excluding: str | None
    vulnerable: bool


def _iter_cpe_matches(configurations: Any) -> list[dict[str, Any]]:
    """Yield every cpeMatch dict from an NVD ``configurations`` payload.

    Handles both the API 2.0 list form (``[{"nodes": [...]}, ...]``) and the
    legacy dict form (``{"nodes": [...]}``), plus nested child nodes.
    """
    if isinstance(configurations, dict):
        config_list: list[Any] = [configurations]
    elif isinstance(configurations, list):
        config_list = configurations
    else:
        return []

    matches: list[dict[str, Any]] = []
    # Walk nodes in document order so nested children are covered too.
    queue: list[Any] = []
    for config in config_list:
        if isinstance(config, dict):
            queue.extend(config.get("nodes", []) or [])

    while queue:
        node = queue.pop(0)
        if not isinstance(node, dict):
            continue
        for cpe_match in node.get("cpeMatch", []) or []:
            if isinstance(cpe_match, dict):
                matches.append(cpe_match)
        queue.extend(node.get("children", []) or [])
    return matches


def _vendor_product_from_criteria(criteria: str) -> tuple[str | None, str | None]:
    """Extract vendor (idx 3) and product (idx 4) from a CPE 2.3 URI."""
    # CPE format: cpe:2.3:a:vendor:product:version:...
    parts = criteria.split(":")
    if len(parts) >= 5:
        return (parts[3] or None), (parts[4] or None)
    return None, None


def parse_cpe_configurations(cve: dict[str, Any]) -> list[CpeCriterion]:
    """Parse all CPE criteria (with version ranges) from an NVD CVE payload.

    Returns one ``CpeCriterion`` per cpeMatch entry, preserving the version-range
    bounds that were previously discarded.
    """
    if not isinstance(cve, dict):
        return []

    criteria_list: list[CpeCriterion] = []
    for cpe_match in _iter_cpe_matches(cve.get("configurations")):
        criteria = cpe_match.get("criteria")
        if not isinstance(criteria, str) or not criteria.strip():
            continue
        vendor, product = _vendor_product_from_criteria(criteria)
        criteria_list.append(
            CpeCriterion(
                cpe_uri=criteria.strip(),
                vendor=vendor,
                product=product,
                version_start_including=cpe_match.get("versionStartIncluding"),
                version_start_excluding=cpe_match.get("versionStartExcluding"),
                version_end_including=cpe_match.get("versionEndIncluding"),
                version_end_excluding=cpe_match.get("versionEndExcluding"),
                vulnerable=bool(cpe_match.get("vulnerable", True)),
            )
        )
    return criteria_list


async def persist_cpe_configurations(
    db: AsyncSession,
    *,
    cve_id: str,
    cve: dict[str, Any],
) -> int:
    """Replace the stored CPE criteria for ``cve_id`` from a raw NVD payload.

    Delete-then-insert keeps the rows idempotent across re-ingest. Returns the
    number of criteria persisted.
    """
    normalized_id = cve_id.strip().upper()
    criteria = parse_cpe_configurations(cve)

    await db.execute(delete(CveCpeMatch).where(CveCpeMatch.cve_id == normalized_id))
    if not criteria:
        return 0

    db.add_all(
        [
            CveCpeMatch(
                cve_id=normalized_id,
                cpe_uri=c["cpe_uri"][:500],
                vendor=c["vendor"],
                product=c["product"],
                version_start_including=c["version_start_including"],
                version_start_excluding=c["version_start_excluding"],
                version_end_including=c["version_end_including"],
                version_end_excluding=c["version_end_excluding"],
                vulnerable=c["vulnerable"],
            )
            for c in criteria
        ]
    )
    return len(criteria)


async def backfill_cpe_configurations(  # noqa: C901
    db: AsyncSession,
    *,
    cve_ids: list[str] | None = None,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    """Fetch CPE configurations from NVD for existing CVEs and persist them.

    Rate-limit-aware: reuses ``fetch_nvd_cve_by_id`` (429 backoff, key fallback)
    and the per-request delay used by the CVE-field backfill. CVEs whose CPE
    rows are newer than ``NVD_CPE_CACHE_TTL_HOURS`` are skipped, and the session
    is committed every ``NVD_CPE_BATCH_SIZE`` rows.
    """
    settings = get_settings()

    stmt = select(CVE.cve_id)
    if cve_ids:
        stmt = stmt.where(CVE.cve_id.in_([c.strip().upper() for c in cve_ids]))

    # Skip CVEs whose CPE rows are still fresh within the TTL window.
    ttl_hours = settings.NVD_CPE_CACHE_TTL_HOURS
    if ttl_hours > 0:
        cutoff = datetime.now(UTC) - timedelta(hours=ttl_hours)
        fresh_subq = (
            select(distinct(CveCpeMatch.cve_id))
            .where(CveCpeMatch.created_at >= cutoff)
            .scalar_subquery()
        )
        stmt = stmt.where(CVE.cve_id.notin_(fresh_subq))

    stmt = stmt.order_by(CVE.cve_id.asc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    results = {"checked": 0, "persisted": 0, "criteria": 0, "missing_upstream": 0}
    per_request_delay_seconds = 1.2 if settings.NVD_API_KEY else 2.0
    commit_every = max(settings.NVD_CPE_BATCH_SIZE, 1)
    total_rows = len(rows)

    if progress_callback is not None:
        progress_callback({**results, "total": total_rows})

    for cve_id in rows:
        results["checked"] += 1
        cve_payload = await fetch_nvd_cve_by_id(cve_id, api_key=settings.NVD_API_KEY)
        if cve_payload is None:
            results["missing_upstream"] += 1
        else:
            count = await persist_cpe_configurations(db, cve_id=cve_id, cve=cve_payload)
            if count:
                results["persisted"] += 1
                results["criteria"] += count

        if results["checked"] % commit_every == 0:
            await db.commit()
            if progress_callback is not None:
                progress_callback({**results, "total": total_rows})

        await asyncio.sleep(per_request_delay_seconds)

    await db.commit()
    if progress_callback is not None:
        progress_callback({**results, "total": total_rows})
    return results


async def count_cpe_criteria(db: AsyncSession, cve_id: str) -> int:
    """Return how many CPE criteria rows are stored for a CVE (test/debug helper)."""
    stmt = (
        select(func.count())
        .select_from(CveCpeMatch)
        .where(CveCpeMatch.cve_id == cve_id.strip().upper())
    )
    return int((await db.execute(stmt)).scalar_one())
