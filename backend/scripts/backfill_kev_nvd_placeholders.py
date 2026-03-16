#!/usr/bin/env python3
"""Backfill KEV-created CVE placeholder rows with official NVD data."""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


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
    parser.add_argument(
        "--commit-every",
        type=int,
        default=25,
        help="Commit and print progress every N processed CVEs",
    )
    args = parser.parse_args()

    today = date.today()

    db = cast(AsyncSession, AsyncSessionLocal())
    async with db:
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

        total_candidates = len(missing_kev_cve_ids)
        print(
            "Starting KEV placeholder backfill: "
            f"candidates={total_candidates} commit_every={args.commit_every}",
            flush=True,
        )

        def report_progress(progress: dict[str, int]) -> None:
            print(
                "KEV backfill progress: "
                f"checked={progress['checked']}/{progress['total']} "
                f"updated={progress['updated']} "
                f"unchanged={progress['unchanged']} "
                f"missing_upstream={progress['missing_upstream']}",
                flush=True,
            )

        result = await backfill_missing_nvd_fields_for_existing_cves(
            db,
            cve_ids=list(missing_kev_cve_ids),
            limit=args.limit,
            max_published_date=today,
            commit_every=args.commit_every,
            progress_callback=report_progress,
        )

    print(
        "KEV placeholder backfill complete: "
        f"checked={result['checked']} updated={result['updated']} "
        f"unchanged={result['unchanged']} missing_upstream={result['missing_upstream']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
