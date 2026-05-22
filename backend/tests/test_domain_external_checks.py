"""Tests for the per-domain external-check cache (Month 1 Phase E2 / #110).

The route persists the merged HIBP/Shodan/OTX/crt.sh payload on the
OrgDomain row and serves cached responses within the 24h TTL. The cache
path is the trust-bearing one — the upstream APIs are paid, so a quiet
cache miss costs money. These tests guard:

1. Within TTL, the route returns ``cached: true`` and does NOT call upstreams.
2. ``force=true`` bypasses the cache and re-runs the checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.db.engine import AsyncSessionLocal
from app.db.org_domain import OrgDomain
from app.db.organization import Organization
from app.db.user import User
from app.main import app


@dataclass
class _Skipped:
    """Stand-in for the skipped-provider dataclass returned by run_tier2_checks."""

    skipped: bool = True


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def admin_org_and_cached_domain():
    """Seed an admin user, an org, and a domain with a fresh cached payload."""
    async with AsyncSessionLocal() as session:
        org = Organization(
            name=_unique("ExtChecksOrg"),
            industry_label="Tech & Software",
            ic3_sector="Technology",
            primary_state="CA",
            employee_range="11-50",
            revenue_range="$1M-$10M",
        )
        session.add(org)
        await session.flush()

        admin = User(
            email=f"{_unique('admin')}@example.com",
            firebase_uid=_unique("uid"),
            role="admin",
            org_id=org.id,
            org_role="owner",
        )
        session.add(admin)
        await session.flush()

        domain = OrgDomain(
            org_id=org.id,
            domain_name=f"{_unique('ex')}.com",
            external_checks_last_at=datetime.now(UTC),
            external_checks_data={
                "hibp": {"skipped": True},
                "shodan": {"skipped": True},
                "otx": {"skipped": True},
                "crtsh": {"subdomains": []},
            },
        )
        session.add(domain)
        await session.commit()
        await session.refresh(domain)
        await session.refresh(admin)
        yield admin, org, domain

        await session.execute(OrgDomain.__table__.delete().where(OrgDomain.id == domain.id))
        await session.execute(User.__table__.delete().where(User.id == admin.id))
        await session.execute(Organization.__table__.delete().where(Organization.id == org.id))
        await session.commit()


@pytest.mark.asyncio
async def test_external_checks_returns_cached_within_ttl(
    client: AsyncClient, admin_org_and_cached_domain
):
    admin, org, domain = admin_org_and_cached_domain

    async def _admin():
        return admin

    app.dependency_overrides[get_current_user] = _admin
    # If the cache short-circuit works, run_tier2_checks must NOT be called.
    sentinel = AsyncMock(side_effect=AssertionError("cache miss: upstreams should not run"))
    try:
        with patch("app.api.routes.v1.domains.run_tier2_checks", sentinel):
            resp = await client.get(
                f"/api/v1/organizations/{org.id}/domains/{domain.id}/external-checks"
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cached"] is True
    assert body["domain"] == domain.domain_name
    sentinel.assert_not_called()


@pytest.mark.asyncio
async def test_external_checks_force_bypasses_cache(
    client: AsyncClient, admin_org_and_cached_domain
):
    admin, org, domain = admin_org_and_cached_domain

    async def _admin():
        return admin

    app.dependency_overrides[get_current_user] = _admin

    upstream = AsyncMock(return_value=(_Skipped(), _Skipped(), _Skipped(), _Skipped()))
    try:
        with patch("app.api.routes.v1.domains.run_tier2_checks", upstream):
            resp = await client.get(
                f"/api/v1/organizations/{org.id}/domains/{domain.id}/external-checks?force=true"
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cached"] is False
    upstream.assert_awaited_once()
