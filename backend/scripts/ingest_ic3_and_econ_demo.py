#!/usr/bin/env python3
"""Demo ingestors for IC3 and economic indicators.

Run from the backend directory (so ``app`` is importable) with the venv activated:

    python scripts/ingest_ic3_and_econ_demo.py
"""

import asyncio
import sys

# Ensure backend package root is on sys.path when run as a script
sys.path.insert(0, ".")

from app.db.engine import AsyncSessionLocal, close_db, init_db  # type: ignore  # noqa: E402
from app.ingestors.econ import ingest_region_economics  # noqa: E402
from app.ingestors.ic3 import ingest_ic3  # noqa: E402


async def main() -> None:
    """Populate IC3 and economics tables with demo data."""
    await init_db()

    # Ingest IC3 demo incidents
    ic3_rows = [
        {"year": 2022, "sector": "Finance", "state": "CA", "loss": 1_200_000.0},
        {"year": 2022, "sector": "Healthcare", "state": "TX", "loss": 750_000.0},
        {"year": 2023, "sector": "Manufacturing", "state": "NY", "loss": 2_500_000.0},
        {"year": 2023, "sector": "Education", "state": "WA", "loss": 150_000.0},
        {"year": 2023, "sector": "Retail", "state": "FL", "loss": 600_000.0},
    ]

    async with AsyncSessionLocal() as session:
        await ingest_ic3(session, ic3_rows)

    # Ingest regional economics from CSV (backend/data/region_econ.csv)
    async with AsyncSessionLocal() as session:
        await ingest_region_economics(session)

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())

