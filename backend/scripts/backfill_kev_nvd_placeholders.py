#!/usr/bin/env python3
"""Backfill KEV-created CVE placeholder rows with official NVD data."""

import argparse
import asyncio
import sys
from datetime import date

from sqlalchemy import select

sys.path.insert(0, ".")


async def main() -> None:
    """Fetch NVD data for KEV-linked CVEs missing CVSS/severity/published fields."""
    from app.db.engine import AsyncSessionLocal
    from app.db.models import CVE, KEV
    from app.ingestors.nvd import backfill_missing_nvd_fields_for_existing_cves

    parser = argparse.ArgumentParser(description="Backfill KEV placeholder CVEs from NVD")
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        help="Maximum number of recent KEV placeholder CVEs to backfill",
    )
    args = parser.parse_args()

    today = date(2026, 3, 11)

    async with AsyncSessionLocal() as db:
        missing_kev_cve_ids = (
            await db.execute(
                select(CVE.cve_id)
                .join(KEV, KEV.cve_id == CVE.cve_id)
                .where(
                    (CVE.cvss_score.is_(None))
                    | (CVE.severity.is_(None))
                    | (CVE.published_date.is_(None))
                )
                .order_by(KEV.due_date.desc().nullslast(), CVE.cve_id.asc())
                .limit(args.limit)
            )
        ).scalars().all()

        result = await backfill_missing_nvd_fields_for_existing_cves(
            db,
            cve_ids=list(missing_kev_cve_ids),
            limit=args.limit,
            max_published_date=today,
        )

    print(
        "KEV placeholder backfill complete: "
        f"checked={result['checked']} updated={result['updated']} "
        f"unchanged={result['unchanged']} missing_upstream={result['missing_upstream']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
