#!/usr/bin/env python3
"""Production ingestors for all real data sources (NVD, IC3, Econ).

This script ingests data from real upstream feeds:
- NVD: National Vulnerability Database API (requires NVD_API_KEY)
- IC3: Published FBI Internet Crime Complaint Center statistics
- Econ: US Census Bureau API (requires CENSUS_API_KEY)

Run from the backend directory with the venv activated:

    python scripts/ingest_real_data.py [--nvd-limit NUM] [--econ] [--ic3-years YEAR,YEAR,...]

Example:
    python scripts/ingest_real_data.py --nvd-limit 5000 --econ --ic3-years 2021,2022,2023
"""

import argparse
import asyncio

import httpx

from app.db.engine import AsyncSessionLocal, close_db, init_db
from app.ingestors.econ import ingest_region_economics
from app.ingestors.ic3_real import ingest_ic3_real
from app.ingestors.nvd import ingest_nvd


async def main() -> None:
    """Populate all tables with real production data."""
    parser = argparse.ArgumentParser(
        description="Ingest real data from NVD, IC3, and Census APIs"
    )
    parser.add_argument(
        "--nvd-limit",
        type=int,
        default=None,
        help="Limit number of CVEs to ingest (default: all available)",
    )
    parser.add_argument(
        "--nvd-start",
        type=int,
        default=0,
        help="Start index for NVD CVE ingestion (default: 0)",
    )
    parser.add_argument(
        "--econ",
        action="store_true",
        help="Ingest economic indicators from Census API",
    )
    parser.add_argument(
        "--ic3-years",
        type=str,
        default="2021,2022,2023",
        help="Comma-separated years for IC3 ingestion (default: 2021,2022,2023)",
    )
    parser.add_argument(
        "--skip-nvd",
        action="store_true",
        help="Skip NVD ingestion",
    )
    parser.add_argument(
        "--skip-ic3",
        action="store_true",
        help="Skip IC3 ingestion",
    )
    parser.add_argument(
        "--ic3-pdf",
        action="store_true",
        default=True,
        help="Fetch IC3 data from official FBI PDF reports (default: True)",
    )
    parser.add_argument(
        "--ic3-fallback",
        action="store_true",
        help="Use hardcoded IC3 data instead of fetching PDFs",
    )

    args = parser.parse_args()

    await init_db()

    print("\n" + "=" * 60)
    print("REAL DATA INGESTION - Production Sources")
    print("=" * 60 + "\n")

    # Ingest NVD data
    if not args.skip_nvd:
        print(f"📥 Ingesting NVD CVEs (limit: {args.nvd_limit or 'all'})...")
        async with AsyncSessionLocal() as session:  # type: ignore
            try:
                await ingest_nvd(
                    session,
                    start_index=args.nvd_start,
                    max_results=args.nvd_limit,
                )
                print("✓ NVD ingestion complete\n")
            except ValueError as e:
                print(f"✗ NVD ingestion failed: {e}\n")
            except httpx.HTTPError as e:
                print(f"✗ NVD ingestion error: {e}\n")

    # Ingest Economic data
    if args.econ:
        print("📥 Ingesting economic indicators from Census API...")
        async with AsyncSessionLocal() as session:  # type: ignore
            try:
                await ingest_region_economics(session)
                print("✓ Economic data ingestion complete\n")
            except (OSError, RuntimeError, ValueError) as e:
                print(f"✗ Economic data ingestion error: {e}\n")

    # Ingest IC3 data
    if not args.skip_ic3:
        years = [int(y.strip()) for y in args.ic3_years.split(",")]
        use_pdf = not args.ic3_fallback  # Use PDF unless --ic3-fallback is set
        print(f"📥 Ingesting IC3 incidents for years {years}...")
        if use_pdf:
            print("   (Fetching from official FBI PDF reports)\n")
        else:
            print("   (Using hardcoded published data)\n")
        async with AsyncSessionLocal() as session:  # type: ignore
            try:
                await ingest_ic3_real(session, years=years, use_pdf=use_pdf)
                print("✓ IC3 ingestion complete\n")
            except (OSError, RuntimeError, ValueError) as e:
                print(f"✗ IC3 ingestion error: {e}\n")

    print("=" * 60)
    print("✓ All ingestions completed!")
    print("=" * 60 + "\n")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
