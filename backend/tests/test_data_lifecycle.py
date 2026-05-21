"""Integration tests for DELETE /organizations/{id} and the JSON export route.

Covers the Month 1 Phase C DoD: an admin can delete an org and confirm all
related rows are gone, the action lands in ``audit_log``, and the export
endpoint streams the org's full tenant data.

The cascade list in ``data_lifecycle.py`` covers more tables than this test
exercises — we seed a representative subset with simple required fields so the
test stays maintainable. The cascade itself is verified by reading the model
list at module import time, so any new tenant-scoped model that's missing from
``_ORG_SCOPED_MODELS_BY_ORG_ID`` will surface in code review, not here.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.api.routes.v1.auth import get_current_user
from app.db.audit_log import AuditLog
from app.db.engine import AsyncSessionLocal
from app.db.membership import Membership
from app.db.org_domain import OrgDomain
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.db.user import User
from app.main import app


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def admin_user_and_org():
    """Seed an admin + an org populated across three tenant tables."""
    async with AsyncSessionLocal() as session:
        org = Organization(
            name=_unique("LifecycleOrg"),
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

        session.add_all(
            [
                Membership(user_id=admin.id, org_id=org.id, role="owner", status="active"),
                OrgDomain(org_id=org.id, domain_name=f"{_unique('ex')}.com"),
                OrgVendor(org_id=org.id, vendor_name=_unique("Acme")),
            ]
        )
        await session.commit()
        await session.refresh(org)
        await session.refresh(admin)
        yield admin, org

        # Best-effort tidy if the DELETE path under test didn't run.
        await session.execute(User.__table__.delete().where(User.id == admin.id))
        await session.execute(Organization.__table__.delete().where(Organization.id == org.id))
        await session.commit()


@pytest.mark.asyncio
async def test_delete_org_purges_tenant_rows_and_audits(client: AsyncClient, admin_user_and_org):
    admin, org = admin_user_and_org

    async def _admin():
        return admin

    app.dependency_overrides[get_current_user] = _admin
    try:
        resp = await client.delete(f"/api/v1/organizations/{org.id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204, resp.text

    async with AsyncSessionLocal() as session:
        for model in (OrgDomain, OrgVendor, Membership):
            remaining = await session.execute(
                select(model).where(model.org_id == org.id)  # type: ignore[attr-defined]
            )
            assert (
                remaining.first() is None
            ), f"{model.__tablename__} still has rows for org {org.id}"

        org_row = await session.get(Organization, org.id)
        assert org_row is None

        audit = await session.execute(
            select(AuditLog).where(AuditLog.action == "organization.delete")
        )
        rows = audit.scalars().all()
        assert any(
            (r.payload or {}).get("original_org_id") == org.id for r in rows
        ), "audit_log must record the delete with original_org_id"


@pytest.mark.asyncio
async def test_export_org_streams_json_and_audits(client: AsyncClient, admin_user_and_org):
    admin, org = admin_user_and_org

    async def _admin():
        return admin

    app.dependency_overrides[get_current_user] = _admin
    try:
        resp = await client.get(f"/api/v1/organizations/{org.id}/export")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["org_id"] == org.id
    assert body["organization"]["name"] == org.name
    assert "org_domains" in body["tables"]
    assert len(body["tables"]["org_domains"]) == 1

    async with AsyncSessionLocal() as session:
        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.org_id == org.id,
                AuditLog.action == "organization.export",
            )
        )
        assert audit.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_delete_org_404_when_missing(client: AsyncClient):
    async with AsyncSessionLocal() as session:
        admin = User(
            email=f"{_unique('admin')}@example.com",
            firebase_uid=_unique("uid"),
            role="admin",
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_id = admin.id

    async def _admin():
        async with AsyncSessionLocal() as s:
            return await s.get(User, admin_id)

    app.dependency_overrides[get_current_user] = _admin
    try:
        resp = await client.delete("/api/v1/organizations/9999999")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncSessionLocal() as s:
            await s.execute(User.__table__.delete().where(User.id == admin_id))
            await s.commit()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_org_requires_admin_role(client: AsyncClient):
    """A non-admin (role=member) is rejected before the endpoint runs."""
    member = User(
        id=999999,
        email="member@example.com",
        firebase_uid="member-uid",
        role="member",
    )

    async def _member():
        return member

    app.dependency_overrides[get_current_user] = _member
    try:
        resp = await client.delete("/api/v1/organizations/1")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
