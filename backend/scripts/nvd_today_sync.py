#!/usr/bin/env python3
import asyncio
import sys
from typing import cast

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, ".")

URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
START = "2026-03-10T00:00:00.000"
END = "2026-03-10T23:59:59.999"


async def main() -> None:
    from app.db.engine import AsyncSessionLocal
    from app.db.models import CVE
    from app.ingestors.nvd import _normalize_nvd_cve

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
            existing = (
                await db.execute(select(CVE).where(CVE.cve_id == cve_id))
            ).scalar_one_or_none()

            if existing is None:
                db.add(
                    CVE(
                        cve_id=cve_id,
                        description=description,
                        cvss_score=cvss_score,
                        severity=severity,
                        published_date=published_date,
                    )
                )
                added += 1
                continue

            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.cvss_score != cvss_score:
                existing.cvss_score = cvss_score
                changed = True
            if existing.severity != severity:
                existing.severity = severity
                changed = True
            if existing.published_date != published_date:
                existing.published_date = published_date
                changed = True
            if changed:
                updated += 1

        await db.commit()

    print(f"NVD today sync complete: feed_total={len(vulnerabilities)} added={added} updated={updated}")


if __name__ == "__main__":
    asyncio.run(main())
