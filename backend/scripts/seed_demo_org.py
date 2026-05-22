"""Seed canonical demo organizations + curated dataset.

Replaces the runtime ``ENABLE_DEMO_MODE`` swap: instead of toggling a global
flag, each demo experience is backed by an organization row with
``is_demo=True``. Repositories check ``organization.is_demo`` and serve from
the curated fixture rather than live data.

Two orgs are seeded:

1. ``Public Demo`` — canonical org used by unauthenticated public routes that
   have no caller-supplied org context. Its id is recorded in the audit log
   the first time it is seeded.
2. ``Sample SMB`` — a representative demo tenant any new viewer account can
   be attached to for product walkthroughs.

Idempotent: rerunning the script is safe and will only insert rows that do
not already exist (matched by name).

Usage::

    cd backend
    python -m scripts.seed_demo_org
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db.asset import Asset
from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal
from app.db.organization import Organization
from app.db.scan_run import ScanRun
from app.db.user import User  # noqa: F401  # registers User mapper for Organization.members

logger = logging.getLogger(__name__)

PUBLIC_DEMO_ORG_NAME = "Public Demo"
SAMPLE_DEMO_ORG_NAME = "Sample SMB"


_DEMO_ORG_SPECS: list[dict[str, object]] = [
    {
        "name": PUBLIC_DEMO_ORG_NAME,
        "industry_label": "Tech & Software",
        "ic3_sector": "Technology",
        "primary_state": "CA",
        "employee_range": "1-10",
        "revenue_range": "<$1M",
        "is_demo": True,
    },
    {
        "name": SAMPLE_DEMO_ORG_NAME,
        "industry_label": "Professional Services",
        "ic3_sector": "Professional Services",
        "primary_state": "NY",
        "employee_range": "11-50",
        "revenue_range": "$1M-$10M",
        "is_demo": True,
    },
]


_DEMO_VENDOR_PRODUCTS: list[tuple[str, str, str | None]] = [
    ("Microsoft", "Windows 11", "23H2"),
    ("Microsoft", "Office 365", "2024"),
    ("Microsoft", "Edge", "121.0"),
    ("Apple", "macOS", "14.3"),
    ("Apple", "Safari", "17.3"),
    ("Google", "Chrome", "121.0"),
    ("Mozilla", "Firefox", "122.0"),
    ("Adobe", "Acrobat Reader", "23.008"),
    ("Zoom", "Zoom Client", "5.17"),
    ("Slack", "Slack Desktop", "4.36"),
    ("Cisco", "AnyConnect", "4.10"),
    ("VMware", "Workstation", "17.5"),
    ("Oracle", "Java Runtime", "21"),
    ("Docker", "Docker Desktop", "4.27"),
    ("GitHub", "GitHub Desktop", "3.3"),
    ("Atlassian", "Jira", "9.12"),
]


def _build_demo_asset_specs(count: int = 25) -> list[dict[str, object]]:
    """Generate ``count`` deterministic fake asset specs."""
    os_pool: list[tuple[str, str]] = [
        ("Windows 11", "23H2"),
        ("Windows 10", "22H2"),
        ("macOS", "14.3"),
        ("macOS", "13.6"),
        ("Ubuntu", "22.04"),
        ("Ubuntu", "20.04"),
    ]
    specs: list[dict[str, object]] = []
    for i in range(1, count + 1):
        os_name, os_version = os_pool[i % len(os_pool)]
        specs.append(
            {
                "hostname": f"demo-host-{i:02d}",
                "ip_address": f"10.10.{(i // 256) % 256}.{i % 256}",
                "os_name": os_name,
                "os_version": os_version,
                "mac_address": f"02:00:00:00:{(i // 256):02x}:{i % 256:02x}",
                "discovered_via": "csv_upload",
                "is_active": True,
            }
        )
    return specs


async def _seed_demo_inventory(session, org: Organization) -> None:
    """Populate ~25 assets + ~80 software rows for the Public Demo org.

    Idempotent: bails early if any asset already exists for the org.
    """
    existing = await session.execute(
        select(Asset).where(Asset.org_id == org.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Demo inventory for %s already present; skipping", org.name)
        return

    scan_run = ScanRun(
        org_id=org.id,
        source="csv_upload",
        status="succeeded",
        asset_count=0,
        software_count=0,
        scan_metadata={"seeded_by": "seed_demo_org.py"},
    )
    session.add(scan_run)
    await session.flush()

    asset_specs = _build_demo_asset_specs(25)
    assets: list[Asset] = []
    for spec in asset_specs:
        asset = Asset(org_id=org.id, **spec)
        session.add(asset)
        assets.append(asset)
    await session.flush()

    software_count = 0
    for idx, asset in enumerate(assets):
        # Each asset gets 3–4 software entries from the rotating vendor pool;
        # ~80 rows total across 25 assets.
        for offset in range(3 + (idx % 2)):
            vendor, product, version = _DEMO_VENDOR_PRODUCTS[
                (idx + offset) % len(_DEMO_VENDOR_PRODUCTS)
            ]
            session.add(
                AssetSoftware(
                    asset_id=asset.id,
                    org_id=org.id,
                    vendor=vendor,
                    product=product,
                    version=version,
                    source="csv_upload",
                )
            )
            software_count += 1

    scan_run.asset_count = len(assets)
    scan_run.software_count = software_count
    await session.commit()
    logger.info(
        "Seeded %d demo assets + %d software rows for %s",
        len(assets),
        software_count,
        org.name,
    )


async def seed_demo_orgs() -> list[Organization]:
    """Insert demo orgs if they don't exist; return the resolved rows."""
    seeded: list[Organization] = []
    async with AsyncSessionLocal() as session:
        for spec in _DEMO_ORG_SPECS:
            existing = await session.execute(
                select(Organization).where(Organization.name == spec["name"])
            )
            org = existing.scalar_one_or_none()
            if org is None:
                org = Organization(**spec)
                session.add(org)
                await session.commit()
                await session.refresh(org)
                logger.info("Seeded demo org %s (id=%s)", org.name, org.id)
            else:
                if not org.is_demo:
                    org.is_demo = True
                    await session.commit()
                    await session.refresh(org)
                    logger.info("Marked existing org %s as is_demo=True", org.name)
                else:
                    logger.info("Demo org %s already present (id=%s)", org.name, org.id)
            if org.name == PUBLIC_DEMO_ORG_NAME:
                await _seed_demo_inventory(session, org)
            seeded.append(org)
    return seeded


async def get_public_demo_org(session) -> Organization | None:
    """Return the canonical Public Demo org row, or None if unseeded."""
    result = await session.execute(
        select(Organization).where(Organization.name == PUBLIC_DEMO_ORG_NAME)
    )
    return result.scalar_one_or_none()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_orgs())
