# app/ingestors/cisa_kev.py
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import KEV

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

async def ingest_cisa_kev(db: AsyncSession):
    async with httpx.AsyncClient() as client:
        resp = await client.get(CISA_KEV_URL)
        data = resp.json()

    for item in data["vulnerabilities"]:
        kev = KEV(
            cve_id=item["cveID"],
            vendor=item["vendorProject"],
            product=item["product"],
            due_date=item.get("dueDate")
        )
        db.add(kev)

    await db.commit()
