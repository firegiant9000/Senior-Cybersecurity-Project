# app/ingestors/ic3.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import IC3Incident

async def ingest_ic3(db: AsyncSession, ic3_rows: list[dict]):
    for row in ic3_rows:
        incident = IC3Incident(
            year=row["year"],
            sector=row["sector"],
            state=row["state"],
            loss_amount=row["loss"]
        )
        db.add(incident)

    await db.commit()
