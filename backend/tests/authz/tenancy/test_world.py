"""The tenancy fixture world is shaped as documented: both role stores, every kind per org."""

import importlib

import pytest
from sqlalchemy import select, text

from app.db.agent_enrollment import AgentEnrollment
from app.db.ai_summary_generation import AISummaryGeneration
from app.db.assessment_submission import AssessmentSubmission
from app.db.asset import Asset
from app.db.asset_finding import AssetFinding
from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal
from app.db.finding_status import FindingStatus
from app.db.findings_snapshot import FindingsSnapshot
from app.db.integration_credential import IntegrationCredential
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.org_domain import OrgDomain
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.scan_run import ScanRun
from app.db.user import User
from tests.authz.tenancy._world import snapshot_org, snapshot_tables


async def _user(user_id: int) -> User:
    async with AsyncSessionLocal() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def _memberships(user_id: int) -> list[Membership]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Membership).where(Membership.user_id == user_id))
        return list(result.scalars())


async def test_roles_consistent_in_both_stores(world):
    for org in (world.a, world.b):
        for role, wu in (("owner", org.owner), ("admin", org.admin), ("member", org.member)):
            user = await _user(wu.user_id)
            memberships = await _memberships(wu.user_id)
            assert user.role == "member"
            assert user.firebase_uid == wu.uid
            assert (user.org_id, user.org_role) == (org.org_id, role)
            assert len(memberships) == 1
            assert (memberships[0].org_id, memberships[0].role, memberships[0].status) == (
                org.org_id,
                role,
                "active",
            )


async def test_split_user_shape(world):
    user = await _user(world.split.user_id)
    assert user.org_id == world.a.org_id
    assert user.org_role == "admin"
    memberships = [m for m in await _memberships(world.split.user_id) if m.status == "active"]
    assert [(m.org_id, m.role) for m in memberships] == [(world.b.org_id, "admin")]
    assert all(m.org_id != world.a.org_id for m in await _memberships(world.split.user_id))


async def test_global_admin_and_no_org_shape(world):
    admin = await _user(world.global_admin.user_id)
    no_org = await _user(world.no_org.user_id)
    assert (admin.org_id, admin.role) == (None, "admin")
    assert (no_org.org_id, no_org.role) == (None, "member")
    assert await _memberships(admin.id) == []
    assert await _memberships(no_org.id) == []


async def test_removed_member_shape(world):
    user = await _user(world.a_removed.user_id)
    assert user.org_id is None
    memberships = await _memberships(world.a_removed.user_id)
    assert [(m.org_id, m.status) for m in memberships] == [(world.a.org_id, "inactive")]


async def test_each_org_owns_every_kind(world):
    checks = [
        ("domain_id", OrgDomain, "org_id"),
        ("vendor_id", OrgVendor, "org_id"),
        ("upload_id", OrgUpload, "org_id"),
        ("scan_run_id", ScanRun, "org_id"),
        ("asset_id", Asset, "org_id"),
        ("asset_software_id", AssetSoftware, "org_id"),
        ("finding_id", AssetFinding, "org_id"),
        ("assessment_id", AssessmentSubmission, "organization_id"),
        ("invite_id", Invitation, "org_id"),
        ("agent_id", AgentEnrollment, "org_id"),
        ("ai_generation_id", AISummaryGeneration, "org_id"),
        ("snapshot_id", FindingsSnapshot, "org_id"),
        ("credential_id", IntegrationCredential, "org_id"),
        ("member_user_id", User, "org_id"),
    ]
    async with AsyncSessionLocal() as session:
        for org in (world.a, world.b, world.c):
            for key, model, column in checks:
                row = (
                    await session.execute(select(model).where(model.id == org.ids[key]))
                ).scalar_one()
                assert getattr(row, column) == org.org_id, f"{org.name}.{key}"
            status = (
                await session.execute(
                    select(FindingStatus).where(
                        FindingStatus.org_id == org.org_id,
                        FindingStatus.stable_key == org.ids["stable_key"],
                    )
                )
            ).scalar_one()
            assert status.org_id == org.org_id
            upload = (
                await session.execute(select(OrgUpload).where(OrgUpload.id == org.ids["upload_id"]))
            ).scalar_one()
            stored = world.upload_dir / str(org.org_id) / upload.stored_filename
            assert stored.is_file()
            assert set(org.ids) >= {k for k, _, _ in checks} | {"stable_key"}
    assert (world.a.counts, world.b.counts, world.c.counts) == (
        {"domains": 2, "vendors": 2, "assets": 2},
        {"domains": 1, "vendors": 1, "assets": 1},
        {"domains": 1, "vendors": 1, "assets": 1},
    )
    assert world.a.ids["domain_id"] == world.a.ids_all["domains"][0]


async def test_world_snapshot_stable(world):
    first = await snapshot_org(world.a.org_id, world.upload_dir)
    second = await snapshot_org(world.a.org_id, world.upload_dir)
    assert first == second
    seeded = [
        "organizations",
        "users",
        "memberships",
        "org_domains",
        "org_vendors",
        "org_uploads",
        "scan_runs",
        "assets",
        "asset_software",
        "asset_findings",
        "assessment_submissions",
        "invitations",
        "agent_enrollments",
        "ai_summary_generations",
        "findings_snapshots",
        "finding_statuses",
        "integration_credentials",
        "files",
    ]
    for name in seeded:
        assert first[name], f"{name} is empty in the snapshot"


async def test_snapshot_covers_every_org_table():
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            text(
                "SELECT DISTINCT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND column_name IN ('org_id', 'organization_id') "
                "AND table_name <> 'alembic_version'"
            )
        )
        live = {r[0] for r in rows}
    covered = {t.name for t in snapshot_tables()}
    assert live <= covered, f"not in snapshot_tables(): {sorted(live - covered)}"
    assert {"organizations", "users"} <= covered


async def test_minted_user_authenticates(world, as_user):
    client = await as_user(world.b.member)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == world.b.member.email


def test_no_egress_stubs_installed(egress_sites):
    assert egress_sites
    for module_name, attr in egress_sites:
        target = getattr(importlib.import_module(module_name), attr)
        assert getattr(target, "_egress_stub", False), f"{module_name}.{attr} is not stubbed"


async def test_snapshot_detects_row_and_file_changes(fresh_world):
    world = fresh_world
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    async with AsyncSessionLocal() as session:
        domain = (
            await session.execute(select(OrgDomain).where(OrgDomain.id == world.a.ids["domain_id"]))
        ).scalar_one()
        domain.is_verified = True
        await session.commit()
    after_row = await snapshot_org(world.a.org_id, world.upload_dir)
    assert after_row["org_domains"] != before["org_domains"]

    extra = world.upload_dir / str(world.a.org_id) / "extra.bin"
    extra.write_bytes(b"x")
    after_file = await snapshot_org(world.a.org_id, world.upload_dir)
    assert after_file["files"] != after_row["files"]


async def _marker_user_count() -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(r"SELECT count(*) FROM users WHERE email LIKE 'a\_owner-hta%'")
        )
        return result.scalar_one()


async def test_failed_build_leaves_no_rows(monkeypatch, tmp_path):
    from app.services import agent_token
    from tests.authz.tenancy._world import build_world

    real_issue = agent_token.issue
    calls = 0

    async def flaky_issue(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        return await real_issue(*args, **kwargs)

    monkeypatch.setattr(agent_token, "issue", flaky_issue)
    before = await _marker_user_count()
    with pytest.raises(RuntimeError, match="boom"):
        await build_world(tmp_path)
    assert await _marker_user_count() == before
