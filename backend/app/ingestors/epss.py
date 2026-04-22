"""EPSS (Exploit Prediction Scoring System) ingestor.

Fetches 30-day exploitation probability scores from FIRST.org for all CVEs in
the database. Scores range 0–1; higher = more likely to be exploited in the wild.

API: https://api.first.org/data/v1/epss
Free, unauthenticated. Supports comma-separated CVE IDs (up to 2000 per request).
"""

import asyncio
import logging

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE

logger = logging.getLogger(__name__)

EPSS_API_URL = "https://api.first.org/data/v1/epss"
BATCH_SIZE = 100  # ~1.6KB URL per batch; FIRST.org rejects URLs >8KB


async def ingest_epss(db: AsyncSession) -> int:
    """Fetch EPSS scores from FIRST.org and update cves.epss_score.

    Returns the count of CVEs updated with non-null scores.
    """
    result = await db.execute(select(CVE.cve_id))
    cve_ids: list[str] = [row[0] for row in result.all()]

    if not cve_ids:
        logger.info("No CVEs in database — skipping EPSS ingest")
        return 0

    logger.info("Fetching EPSS scores for %d CVEs", len(cve_ids))

    scores: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(cve_ids), BATCH_SIZE):
            batch = cve_ids[i : i + BATCH_SIZE]
            cve_param = ",".join(batch)
            try:
                resp = await client.get(EPSS_API_URL, params={"cve": cve_param})
                resp.raise_for_status()
                payload = resp.json()
                for entry in payload.get("data", []):
                    cve_id = entry.get("cve")
                    epss_raw = entry.get("epss")
                    if cve_id and epss_raw is not None:
                        try:
                            scores[cve_id] = float(epss_raw)
                        except (ValueError, TypeError):
                            pass
            except httpx.HTTPError as exc:
                logger.warning("EPSS batch %d failed: %s", i // BATCH_SIZE, exc)
                continue
            await asyncio.sleep(0.5)

    if not scores:
        logger.warning("EPSS ingest returned no scores")
        return 0

    updated = 0
    for cve_id, score in scores.items():
        await db.execute(
            update(CVE).where(CVE.cve_id == cve_id).values(epss_score=score)
        )
        updated += 1

    await db.commit()
    logger.info("EPSS ingest complete: %d scores updated", updated)
    return updated
