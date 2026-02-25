# app/ingestors/nvd.py
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CVE

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

async def ingest_nvd(db: AsyncSession):
    async with httpx.AsyncClient() as client:
        resp = await client.get(NVD_URL, params={"resultsPerPage": 50})
        data = resp.json()

    for item in data["vulnerabilities"]:
        cve_data = item["cve"]

        cve = CVE(
            cve_id=cve_data["id"],
            description=cve_data["descriptions"][0]["value"],
            cvss_score=None,  # parse later
            severity=None,
            published_date=None,
        )
        db.add(cve)

    await db.commit()
