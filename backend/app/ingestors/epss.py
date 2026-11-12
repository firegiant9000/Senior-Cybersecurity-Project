"""EPSS (Exploit Prediction Scoring System) ingestor.

Fetches 30-day exploitation probability scores from FIRST.org for all CVEs in
the database. Scores range 0–1; higher = more likely to be exploited in the wild.

API: https://api.first.org/data/v1/epss
Free, unauthenticated. Supports comma-separated CVE IDs (up to 2000 per request).
"""

import asyncio
import datetime
import logging
import math

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE

logger = logging.getLogger(__name__)

EPSS_API_URL = "https://api.first.org/data/v1/epss"
BATCH_SIZE = 100  # ~1.6KB URL per batch; FIRST.org rejects URLs >8KB


def _valid_probability(value: object) -> float | None:
    """Return ``value`` as a finite float in [0.0, 1.0], else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


async def ingest_epss(db: AsyncSession) -> int:  # noqa: C901
    """Fetch EPSS scores from FIRST.org and update cves.epss_score.

    Returns the count of CVEs updated with non-null scores.
    """
    result = await db.execute(select(CVE.cve_id))
    cve_ids: list[str] = [row[0] for row in result.all()]

    if not cve_ids:
        logger.info("No CVEs in database — skipping EPSS ingest")
        return 0

    logger.info("Fetching EPSS scores for %d CVEs", len(cve_ids))

    scores: dict[str, tuple[float, float | None]] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(cve_ids), BATCH_SIZE):
            batch = cve_ids[i : i + BATCH_SIZE]
            requested = set(batch)
            cve_param = ",".join(batch)
            skipped_invalid = 0
            skipped_unrequested = 0
            try:
                resp = await client.get(EPSS_API_URL, params={"cve": cve_param})
                resp.raise_for_status()
                payload = resp.json()
                for entry in payload.get("data", []):
                    cve_id = entry.get("cve")
                    if not isinstance(cve_id, str) or cve_id not in requested:
                        skipped_unrequested += 1
                        continue
                    score = _valid_probability(entry.get("epss"))
                    if score is None:
                        skipped_invalid += 1
                        continue
                    percentile = _valid_probability(entry.get("percentile"))
                    scores[cve_id] = (score, percentile)
                if skipped_invalid or skipped_unrequested:
                    logger.warning(
                        "EPSS batch %d: skipped %d invalid, %d unrequested entries",
                        i // BATCH_SIZE,
                        skipped_invalid,
                        skipped_unrequested,
                    )
            except httpx.HTTPError as exc:
                logger.warning("EPSS batch %d failed: %s", i // BATCH_SIZE, exc)
                continue
            await asyncio.sleep(0.5)

    if not scores:
        logger.warning("EPSS ingest returned no scores")
        return 0

    fetched_at = datetime.datetime.now(datetime.UTC)
    updated = 0
    for cve_id, (score, percentile) in scores.items():
        await db.execute(
            update(CVE)
            .where(CVE.cve_id == cve_id)
            .values(
                epss_score=score,
                epss_percentile=percentile,
                epss_fetched_at=fetched_at,
            )
        )
        updated += 1

    await db.commit()
    logger.info("EPSS ingest complete: %d scores updated", updated)
    return updated
