#!/usr/bin/env python3
"""Quick test script to verify API connectivity and data."""
import asyncio
import sys
sys.path.insert(0, ".")

from app.db.engine import AsyncSessionLocal
from sqlalchemy import select, func
from app.db.models import CVE, IC3Incident, EconomicIndicator


async def test_database():
    """Test database connection and verify real data is present."""
    print("\n" + "="*60)
    print("API DATA VERIFICATION TEST")
    print("="*60 + "\n")

    async with AsyncSessionLocal() as session:
        # Count records
        cve_result = await session.execute(select(func.count(CVE.id)))
        ic3_result = await session.execute(select(func.count(IC3Incident.id)))
        econ_result = await session.execute(select(func.count(EconomicIndicator.id)))

        cve_count = cve_result.scalar()
        ic3_count = ic3_result.scalar()
        econ_count = econ_result.scalar()

        print("✅ Database Connection: SUCCESS\n")

        print("📊 DATA IN DATABASE:")
        print(f"   CVEs:                  {cve_count:>6,}")
        print(f"   IC3 Incidents:         {ic3_count:>6,}")
        print(f"   Economic Indicators:   {econ_count:>6,}")
        print(f"   {'─' * 35}")
        print(f"   TOTAL:                 {cve_count + ic3_count + econ_count:>6,}\n")

        # Sample CVEs
        cve_result = await session.execute(select(CVE).limit(3))
        cves = cve_result.scalars().all()

        print("📋 SAMPLE CVEs:")
        for cve in cves:
            print(f"   • {cve.cve_id} | Severity: {cve.severity} | CVSS: {cve.cvss_score}")
        print()

        # Sample IC3
        ic3_result = await session.execute(select(IC3Incident).limit(3))
        ic3s = ic3_result.scalars().all()

        print("🚨 SAMPLE IC3 INCIDENTS:")
        for incident in ic3s:
            print(f"   • {incident.year} {incident.state} {incident.sector} | ${incident.loss_amount:,.0f}")
        print()

        # Sample Economic
        econ_result = await session.execute(select(EconomicIndicator).limit(3))
        econs = econ_result.scalars().all()

        print("💰 SAMPLE ECONOMIC INDICATORS:")
        for econ in econs:
            print(f"   • {econ.state} | SMBs: {econ.smb_count:,} | Revenue: ${econ.avg_revenue:.2e}")
        print()

        print("="*60)
        print("✓ DATABASE VERIFICATION COMPLETE")
        print("="*60 + "\n")

        return cve_count, ic3_count, econ_count


if __name__ == "__main__":
    asyncio.run(test_database())
