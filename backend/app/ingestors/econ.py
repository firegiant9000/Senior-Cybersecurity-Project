"""Economic indicator ingestion."""

import csv
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import EconomicIndicator

async def ingest_region_economics(
    db: AsyncSession,
    path: str = "data/region_econ.csv",
) -> None:
    """Ingest regional economic indicators from a CSV file."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.add(EconomicIndicator(
                state=row["Region"],
                smb_count=int(row["SMB_Count"]),
                avg_revenue=float(row["GDP"]),
            ))
    await db.commit()
