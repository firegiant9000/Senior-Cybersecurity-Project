"""Seeded multi-organization world for the tenancy sweeps.

Three organizations (A, B, C) with distinct, marker-tagged rows of every
organization-scoped kind, plus users that exercise both role stores (the legacy
`users.org_id/org_role` columns and the `memberships` table).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.schema import Table

from app.db.activation_event import ActivationEvent
from app.db.ai_summary_generation import AISummaryGeneration
from app.db.assessment_submission import AssessmentSubmission
from app.db.asset import Asset
from app.db.asset_finding import AssetFinding
from app.db.asset_software import AssetSoftware
from app.db.audit_log import AuditLog
from app.db.base import Base
from app.db.engine import AsyncSessionLocal
from app.db.finding_status import FindingStatus
from app.db.findings_snapshot import FindingsSnapshot
from app.db.integration_credential import IntegrationCredential
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.org_domain import OrgDomain
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.db.scan_run import ScanRun
from app.db.user import User
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.schemas.assessment_submission import AssessmentSubmissionCreate
from app.services import agent_token

# A str, because the app calls `.encode()` on settings.M365_FERNET_KEY.
_TEST_FERNET_KEY: str = Fernet.generate_key().decode()

# Distinct per org so responses that carry no seeded string (e.g. loss projection) still show
# whose profile they were built from.
ORG_STATES: dict[str, str] = {"A": "TX", "B": "CA", "C": "NY"}

_CSV_BYTES = b"hostname,vendor,product,version\nhost-1,Acme,Widget,1.0\n"


@dataclass(frozen=True)
class WorldUser:
    key: str
    uid: str
    email: str
    user_id: int


@dataclass(frozen=True)
class OrgWorld:
    name: str
    org_id: int
    marker: str
    owner: WorldUser | None
    admin: WorldUser | None
    member: WorldUser | None
    ids: dict[str, int | str]
    ids_all: dict[str, list[int]]
    counts: dict[str, int]


@dataclass(frozen=True)
class World:
    a: OrgWorld
    b: OrgWorld
    c: OrgWorld
    global_admin: WorldUser
    no_org: WorldUser
    split: WorldUser
    a_removed: WorldUser
    upload_dir: Path
    # Marker of the cross-cutting users (global admin, no-org, split, removed): they belong to no
    # single org, so none of an org's markers may appear in their emails.
    shared_marker: str

    def org(self, name: str) -> OrgWorld:
        return {"A": self.a, "B": self.b, "C": self.c}[name]

    def users(self) -> list[WorldUser]:
        org_users = [
            u
            for o in (self.a, self.b, self.c)
            for u in (o.owner, o.admin, o.member)
            if u is not None
        ]
        return [*org_users, self.global_admin, self.no_org, self.split, self.a_removed]


def _assessment_data(marker: str) -> dict:
    payload = AssessmentSubmissionCreate.model_validate(
        {
            "organization_id": 1,
            "status": "Draft",
            "data": {
                "company_profile": {
                    "primary_contact_name": f"{marker} contact",
                    "primary_contact_email": f"contact-{marker}@example.com",
                    "employee_count": 25,
                    "annual_revenue_usd": 1_000_000,
                    "critical_assets": [marker],
                },
                "security_controls": {
                    "mfa_enabled": True,
                    "endpoint_protection": True,
                    "backup_strategy": f"{marker} nightly",
                    "incident_response_plan": False,
                },
                "risk_assessment": {
                    "top_risks": [marker],
                    "compliance_requirements": [],
                    "notes": marker,
                },
            },
        }
    )
    return payload.data.model_dump(mode="json")


def _new_user(key: str, marker: str, *, role: str, org_id: int | None, org_role: str | None):
    uid = f"authz-{marker}-{key}"
    email = f"{key}-{marker}@example.com"
    user = User(
        firebase_uid=uid,
        email=email,
        role=role,
        org_id=org_id,
        org_role=org_role,
        auth_provider="password",
        is_active=True,
    )
    return user, uid, email


def _world_user(pending: dict[str, tuple[User, str, str]], key: str) -> WorldUser:
    user, uid, email = pending[key]
    return WorldUser(key=key, uid=uid, email=email, user_id=user.id)


def _staff(
    name: str, pending: dict[str, tuple[User, str, str]]
) -> tuple[WorldUser | None, WorldUser | None, WorldUser | None, int]:
    """(owner, admin, member, member_user_id); C has only a bare member nobody signs in as."""
    if name == "C":
        return None, None, None, pending["c_member"][0].id
    lower = name.lower()
    return (
        _world_user(pending, f"{lower}_owner"),
        _world_user(pending, f"{lower}_admin"),
        _world_user(pending, f"{lower}_member"),
        pending[f"{lower}_member"][0].id,
    )


async def _seed_people(
    session: AsyncSession, orgs: dict[str, Organization], markers: dict[str, str]
) -> dict[str, tuple[User, str, str]]:
    """Users and memberships. `split` and `a_removed` are the deliberate store disagreements."""
    pending: dict[str, tuple[User, str, str]] = {}
    for name in ("A", "B"):
        for role in ("owner", "admin", "member"):
            key = f"{name.lower()}_{role}"
            pending[key] = _new_user(
                key, markers[name], role="member", org_id=orgs[name].id, org_role=role
            )
    pending["c_member"] = _new_user(
        "c_member", markers["C"], role="member", org_id=orgs["C"].id, org_role="member"
    )
    shared = markers["X"]
    pending["global_admin"] = _new_user(
        "global_admin", shared, role="admin", org_id=None, org_role=None
    )
    pending["no_org"] = _new_user("no_org", shared, role="member", org_id=None, org_role=None)
    pending["split"] = _new_user(
        "split", shared, role="member", org_id=orgs["A"].id, org_role="admin"
    )
    pending["a_removed"] = _new_user("a_removed", shared, role="member", org_id=None, org_role=None)
    for user, _uid, _email in pending.values():
        session.add(user)
    await session.flush()

    # (user key, org, role, status)
    memberships = [
        (f"{n.lower()}_{r}", n, r, "active")
        for n in ("A", "B")
        for r in ("owner", "admin", "member")
    ]
    memberships += [
        ("c_member", "C", "member", "active"),
        ("split", "B", "admin", "active"),
        ("a_removed", "A", "admin", "inactive"),
    ]
    for key, org_name, role, status in memberships:
        session.add(
            Membership(
                user_id=pending[key][0].id, org_id=orgs[org_name].id, role=role, status=status
            )
        )
    await session.flush()
    return pending


async def build_world(upload_dir: Path, *, tag: str | None = None) -> World:
    """Seed the world. On any failure, purge whatever was already committed, then re-raise.

    The purge matters because `agent_token.issue` commits mid-build. `tag` replaces the random
    part of every marker, so a test can find exactly this build's rows; it must be unique.
    """
    hex8 = tag or uuid.uuid4().hex[:8]
    # A, B, C name the orgs; X names the cross-cutting users and belongs to no org.
    markers = {n: f"ht{n.lower()}{hex8}" for n in ("A", "B", "C", "X")}
    try:
        return await _build(markers, upload_dir)
    except BaseException:
        await _purge(list(markers.values()), [], [])
        raise


async def _build(markers: dict[str, str], upload_dir: Path) -> World:
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        orgs: dict[str, Organization] = {}
        for name in ("A", "B", "C"):
            marker = markers[name]
            org = Organization(
                name=f"{marker} Org",
                industry_label="Technology",
                ic3_sector="Information Technology",
                primary_state=ORG_STATES[name],
                employee_range="11-50",
                revenue_range="1M-10M",
                primary_domain=f"{marker}.example.com",
                security_controls={"mfa": "yes", "backups": "yes", "edr": "unsure"},
                compliance_frameworks=["SOC2"],
                data_types=["customer"],
                intake_skipped_steps=[f"{marker}-skipped"],
            )
            session.add(org)
            orgs[name] = org
        await session.flush()

        pending = await _seed_people(session, orgs, markers)

        def wu(key: str) -> WorldUser:
            return _world_user(pending, key)

        org_worlds: dict[str, OrgWorld] = {}
        for name in ("A", "B", "C"):
            org = orgs[name]
            marker = markers[name]
            org_id = org.id
            owner, admin, member, member_user_id = _staff(name, pending)
            owner_id = owner.user_id if owner else None

            domains = [OrgDomain(org_id=org_id, domain_name=f"{marker}.example.com")]
            vendors = [
                OrgVendor(org_id=org_id, vendor_name=f"{marker}-v1", product_name=f"{marker}-p")
            ]
            # Every org gets a near-duplicate vendor pair, so the validation report quotes its own
            # marker; A has one more vendor (and domain) than B and C.
            vendors.append(
                OrgVendor(org_id=org_id, vendor_name=f"{marker}-v1b", product_name=f"{marker}-p")
            )
            if name == "A":
                domains.append(OrgDomain(org_id=org_id, domain_name=f"d2.{marker}.example.com"))
                vendors.append(
                    OrgVendor(
                        org_id=org_id, vendor_name=f"{marker}-v1c", product_name=f"{marker}-p"
                    )
                )
            session.add_all([*domains, *vendors])

            stored = f"{marker}.csv"
            org_dir = upload_dir / str(org_id)
            org_dir.mkdir(parents=True, exist_ok=True)
            csv_bytes = _CSV_BYTES + f"{marker}-host,Acme,Widget,1.0\n".encode()
            (org_dir / stored).write_bytes(csv_bytes)
            upload = OrgUpload(
                org_id=org_id,
                uploaded_by=owner_id,
                original_filename=f"{marker}-inventory.csv",
                stored_filename=stored,
                file_size_bytes=len(csv_bytes),
                content_type="text/csv",
                upload_purpose="inventory",
            )
            scan_run = ScanRun(
                org_id=org_id,
                source="csv_upload",
                status="succeeded",
                finished_at=now,
                asset_count=1,
                software_count=1,
                scan_metadata={"marker": marker},
                triggered_by_user_id=owner_id,
            )
            snapshot = FindingsSnapshot(
                org_id=org_id,
                generated_at=now,
                findings=[{"marker": marker, "title": f"{marker} finding"}],
                summary={"total": 1, "by_type": {marker: 1}, "by_severity": {"medium": 1}},
                assessment_tier="enhanced",
                data_sources_used=["seed"],
            )
            status_row = FindingStatus(
                org_id=org_id,
                stable_key=f"{marker}-key",
                status="done",
                title=f"{marker} finding",
                severity="medium",
            )
            credential = IntegrationCredential(
                org_id=org_id,
                connected_by_user_id=owner_id,
                provider="m365",
                status="active",
                tenant_id=marker,
                account_label=f"{marker} tenant",
                scopes="DeviceManagementManagedDevices.Read.All offline_access",
                refresh_token_encrypted=Fernet(_TEST_FERNET_KEY)
                .encrypt(f"refresh-{marker}".encode())
                .decode(),
            )
            invitation = Invitation(
                email=f"invitee-{marker}@example.com",
                org_id=org_id,
                inviter_id=owner_id,
                role="member",
                token=secrets.token_urlsafe(32),
                status="pending",
                expires_at=now + timedelta(days=3),
            )
            assessment = AssessmentSubmission(
                organization_id=org_id,
                status="Draft",
                data=_assessment_data(marker),
                version=1,
                is_current=True,
            )
            session.add_all(
                [upload, scan_run, snapshot, status_row, credential, invitation, assessment]
            )
            await session.flush()

            assets = [
                Asset(
                    org_id=org_id,
                    hostname=f"{marker}-h1",
                    discovered_via="csv_upload",
                    tags=[marker],
                    created_by_scan_run_id=scan_run.id,
                )
            ]
            if name == "A":
                assets.append(
                    Asset(
                        org_id=org_id,
                        hostname=f"{marker}-h1b",
                        discovered_via="csv_upload",
                        tags=[marker],
                        created_by_scan_run_id=scan_run.id,
                    )
                )
            session.add_all(assets)
            await session.flush()

            software = AssetSoftware(
                asset_id=assets[0].id,
                org_id=org_id,
                vendor=f"{marker}-vendor",
                product=f"{marker}-product",
                version="1.0",
                source="csv_upload",
                created_by_scan_run_id=scan_run.id,
            )
            session.add(software)
            await session.flush()

            finding = AssetFinding(
                org_id=org_id,
                asset_id=assets[0].id,
                asset_software_id=software.id,
                cve_id="CVE-2024-0001",
                software_vendor=software.vendor,
                software_product=software.product,
                severity="high",
                risk_score=7.5,
                match_confidence="exact",
                status="open",
            )
            generation = AISummaryGeneration(
                org_id=org_id,
                model_name=f"{marker}-model",
                source="fallback",
                status="success",
                prompt_inputs={"marker": marker},
                output_text=f"{marker} summary",
                findings_snapshot_id=snapshot.id,
                triggered_by_user_id=owner_id,
            )
            session.add_all([finding, generation])
            await session.flush()

            issued = await agent_token.issue(
                SqlAgentEnrollmentRepository(session),
                org_id=org_id,
                name=f"{marker}-agent",
                scopes=["scan:upload"],
                created_by_user_id=owner_id,
            )

            org_worlds[name] = OrgWorld(
                name=name,
                org_id=org_id,
                marker=marker,
                owner=owner,
                admin=admin,
                member=member,
                ids={
                    "domain_id": domains[0].id,
                    "vendor_id": vendors[0].id,
                    "upload_id": upload.id,
                    "scan_run_id": scan_run.id,
                    "asset_id": assets[0].id,
                    "asset_software_id": software.id,
                    "finding_id": finding.id,
                    "assessment_id": assessment.id,
                    "invite_id": invitation.id,
                    "agent_id": issued.enrollment.id,
                    "ai_generation_id": generation.id,
                    "snapshot_id": snapshot.id,
                    "stable_key": status_row.stable_key,
                    "credential_id": credential.id,
                    "member_user_id": member_user_id,
                },
                ids_all={
                    "domains": [d.id for d in domains],
                    "vendors": [v.id for v in vendors],
                    "assets": [a.id for a in assets],
                },
                counts={"domains": len(domains), "vendors": len(vendors), "assets": len(assets)},
            )

        await session.commit()

        return World(
            a=org_worlds["A"],
            b=org_worlds["B"],
            c=org_worlds["C"],
            global_admin=wu("global_admin"),
            no_org=wu("no_org"),
            split=wu("split"),
            a_removed=wu("a_removed"),
            upload_dir=upload_dir,
            shared_marker=markers["X"],
        )


async def drop_world(world: World) -> None:
    org_ids = [world.a.org_id, world.b.org_id, world.c.org_id]
    user_ids = [u.user_id for u in world.users()]
    user_ids.append(int(world.c.ids["member_user_id"]))
    markers = [o.marker for o in (world.a, world.b, world.c)]
    await _purge([*markers, world.shared_marker], org_ids, user_ids)


async def _purge(markers: list[str], org_ids: list[int], user_ids: list[int]) -> None:
    """Delete everything a world created, found by id and by marker (name / email).

    The marker sweep also catches rows a test created later (e.g. a user auto-created by
    accepting an invite) and anything left by a half-finished build.
    """
    if not markers or any(not m or not m.strip() for m in markers):
        raise ValueError("refusing to purge with an empty marker (LIKE '%%' matches every user)")
    async with AsyncSessionLocal() as session:
        await session.rollback()
        org_ids = [
            *org_ids,
            *(
                await session.execute(
                    select(Organization.id).where(
                        Organization.name.in_([f"{m} Org" for m in markers])
                    )
                )
            ).scalars(),
        ]
        marker_match = or_(*(User.email.like(f"%{m}%") for m in markers))
        user_ids = [
            *user_ids,
            *(await session.execute(select(User.id).where(marker_match))).scalars(),
        ]
        await session.execute(
            delete(AuditLog).where(
                or_(AuditLog.org_id.in_(org_ids), AuditLog.actor_user_id.in_(user_ids))
            )
        )
        await session.execute(
            delete(ActivationEvent).where(
                or_(ActivationEvent.org_id.in_(org_ids), ActivationEvent.user_id.in_(user_ids))
            )
        )
        await session.execute(delete(Organization).where(Organization.id.in_(org_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()

        leftovers = (
            await session.execute(select(func.count()).select_from(User).where(marker_match))
        ).scalar_one()
        assert leftovers == 0, "world users survived drop_world"


def snapshot_tables() -> list[Table]:
    """Every org-scoped table, derived from the metadata so new tables are covered."""
    tables = [
        t
        for t in Base.metadata.sorted_tables
        if t.name in ("organizations", "users") or "org_id" in t.c or "organization_id" in t.c
    ]
    return sorted(tables, key=lambda t: t.name)


def _org_filter(table: Table, org_id: int):
    if table.name == "organizations":
        return table.c.id == org_id
    if "org_id" in table.c:
        return table.c.org_id == org_id
    return table.c.organization_id == org_id


async def snapshot_org(org_id: int, upload_dir: Path) -> dict[str, list[tuple]]:
    """Every column of every org-scoped row, `repr`'d and ordered by primary key."""
    result: dict[str, list[tuple]] = {}
    async with AsyncSessionLocal() as session:
        for table in snapshot_tables():
            query = (
                select(table).where(_org_filter(table, org_id)).order_by(*table.primary_key.columns)
            )
            rows = (await session.execute(query)).all()
            result[table.name] = [tuple(repr(v) for v in row) for row in rows]
    files = []
    org_dir = upload_dir / str(org_id)
    if org_dir.is_dir():
        for path in sorted(p for p in org_dir.rglob("*") if p.is_file()):
            files.append(
                (str(path.relative_to(org_dir)), hashlib.sha256(path.read_bytes()).hexdigest())
            )
    result["files"] = files
    return result
