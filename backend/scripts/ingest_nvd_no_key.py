#!/usr/bin/env python3
"""Ingest NVD CVEs without API key (rate limited but functional).

Run from the backend directory with the venv activated:

    python scripts/ingest_nvd_no_key.py --limit 100
"""

import asyncio
import argparse
import sys

sys.path.insert(0, ".")

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import AsyncSessionLocal, close_db, init_db
from app.db.models import CVE


NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


async def ingest_nvd_no_key(db: AsyncSession, max_results: int = 100):
    """
    Ingest CVEs from NVD API without API key.
    
    Note: Without API key, rate limit is 1 request per 6 seconds.
    This is slow but functional for testing.
    
    Args:
        db: Database session
        max_results: Maximum number of CVEs to ingest
    """
    total_fetched = 0
    current_index = 0
    request_count = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while total_fetched < max_results:
            params = {
                "startIndex": current_index,
                "resultsPerPage": min(2000, max_results - total_fetched),
            }

            print(f"📥 Fetching CVEs {current_index}-{current_index + 2000}...", end="", flush=True)
            
            resp = await client.get(NVD_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            request_count += 1

            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                print(" (no more data)")
                break

            for item in vulnerabilities:
                if total_fetched >= max_results:
                    break

                cve_data = item["cve"]
                cve_id = cve_data["id"]
                
                # Check if CVE already exists
                existing = await db.execute(select(CVE).where(CVE.cve_id == cve_id))
                if existing.scalar_one_or_none():
                    continue  # Skip duplicate
                
                # Parse CVSS score
                cvss_score = None
                severity = None
                if "metrics" in cve_data:
                    cvss_v3 = cve_data["metrics"].get("cvssMetricV31") or \
                              cve_data["metrics"].get("cvssMetricV30") or \
                              cve_data["metrics"].get("cvssMetricV2")
                    if cvss_v3:
                        cvss_data = cvss_v3[0] if isinstance(cvss_v3, list) else cvss_v3
                        cvss_score = cvss_data.get("cvssData", {}).get("baseScore")
                        severity = cvss_data.get("cvssData", {}).get("baseSeverity")

                description = "No description available"
                if cve_data.get("descriptions"):
                    description = cve_data["descriptions"][0]["value"]

                try:
                    cve = CVE(
                        cve_id=cve_id,
                        description=description,
                        cvss_score=cvss_score,
                        severity=severity,
                        published_date=None,
                    )
                    db.add(cve)
                    total_fetched += 1
                except ValueError as e:
                    print(f"\n⚠️  Skipping CVE {cve_id}: {e}")
                    continue

            try:
                await db.commit()
            except ValueError as e:
                print(f"\n⚠️  Database commit error: {e}")
                await db.rollback()
            print(f" ✓ ({total_fetched}/{max_results})")

            # Rate limiting: NVD allows 1 request per 6 seconds without API key
            if total_fetched < max_results:
                print("⏳ Rate limiting... (6 sec delay per NVD policy)", flush=True)
                await asyncio.sleep(6)

            current_index += 2000

    print(f"\n✓ Ingested {total_fetched} CVEs ({request_count} API requests)")
    return total_fetched


async def main() -> None:
    """Main entry point for NVD CVE ingestion."""
    parser = argparse.ArgumentParser(description="Ingest NVD CVEs without API key")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of CVEs to ingest (default: 100)",
    )
    args = parser.parse_args()

    await init_db()

    print("\n" + "=" * 60)
    print("NVD CVE INGESTION (No API Key - Rate Limited)")
    print("=" * 60 + "\n")

    async with AsyncSessionLocal() as session:  # type: ignore
        try:
            count = await ingest_nvd_no_key(session, max_results=args.limit)
            print(f"\n✓ Successfully ingested {count} CVEs\n")
        except (OSError, RuntimeError, ValueError, httpx.HTTPError) as e:  # type: ignore
            print(f"\n✗ Ingestion failed: {e}\n")

    print("=" * 60)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
