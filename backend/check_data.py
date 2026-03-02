#!/usr/bin/env python3
"""Check database record counts."""
import asyncio
import sys
sys.path.insert(0, ".")

from app.db.engine import AsyncSessionLocal
from sqlalchemy import select, func
from app.db.models import CVE, IC3Incident, EconomicIndicator


async def check_counts():
    async with AsyncSessionLocal() as session:
        cve_result = await session.execute(select(func.count(CVE.id)))
        ic3_result = await session.execute(select(func.count(IC3Incident.id)))
        econ_result = await session.execute(select(func.count(EconomicIndicator.id)))
        
        cve_count = cve_result.scalar()
        ic3_count = ic3_result.scalar()
        econ_count = econ_result.scalar()
        total = cve_count + ic3_count + econ_count
        
        print("\n✅ Real Data in Your Database:\n")
        print(f"   CVEs:                  {cve_count:>6,}")
        print(f"   IC3 Incidents:         {ic3_count:>6,}")
        print(f"   Economic Indicators:   {econ_count:>6,}")
        print(f"   {'─' * 35}")
        print(f"   TOTAL:                 {total:>6,} records\n")
        
        # Sample data
        cve_sample = await session.execute(select(CVE).limit(1))
        cve = cve_sample.scalar_one_or_none()
        if cve:
            print("📝 Sample CVE:")
            print(f"   ID: {cve.cve_id}")
            print(f"   Severity: {cve.severity}")
            print(f"   CVSS Score: {cve.cvss_score}")
            print(f"   Description: {cve.description[:60]}...\n")


if __name__ == "__main__":
    asyncio.run(check_counts())
