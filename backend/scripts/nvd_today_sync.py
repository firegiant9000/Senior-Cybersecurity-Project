#!/usr/bin/env python3
"""One-off bounded NVD sync for a single publication date window."""

import asyncio
import sys
from datetime import date as _date
from pathlib import Path
from typing import cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_sync_date = _date.today()
START = f"{_sync_date.isoformat()}T00:00:00.000"
END = f"{_sync_date.isoformat()}T23:59:59.999"


async def main() -> None:
    """Fetch and upsert NVD CVEs for the configured day window."""
    from app.db.engine import AsyncSessionLocal
    from app.ingestors.nvd import _normalize_nvd_cve, upsert_normalized_cve

    params = {
        "pubStartDate": START,
        "pubEndDate": END,
        "resultsPerPage": 2000,
        "startIndex": 0,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    vulnerabilities = payload.get("vulnerabilities", [])
    added = 0
    updated = 0

    db_session = cast(AsyncSession, AsyncSessionLocal())
    async with db_session as db:
        for item in vulnerabilities:
            cve_data = item.get("cve", {})
            normalized = _normalize_nvd_cve(cve_data)
            if normalized is None:
                continue

            cve_id, description, cvss_score, severity, published_date = normalized
            status, _ = await upsert_normalized_cve(
                db,
                cve_id=cve_id,
                description=description,
                cvss_score=cvss_score,
                severity=severity,
                published_date=published_date,
            )
            if status == "inserted":
                added += 1
            elif status == "updated":
                updated += 1

        await db.commit()

    print(f"NVD today sync complete: feed_total={len(vulnerabilities)} added={added} updated={updated}")


if __name__ == "__main__":
    asyncio.run(main())

