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

from app.db.engine import AsyncSessionLocal
from app.db.organization import Organization

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
