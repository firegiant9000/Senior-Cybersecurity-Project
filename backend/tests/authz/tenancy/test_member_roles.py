"""Owner-only role management: only an owner can grant, change or remove admin and owner roles.

Every request goes through a minted token. Admins manage plain members; anything that touches the
admin or owner role (inviting as admin, promoting, demoting, removing an admin or owner, an admin
changing itself) is refused with 403 "Owner role required", and a refused request changes nothing.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, event, select, update

from app.db.engine import AsyncSessionLocal, engine
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.user import User
from tests.authz.tenancy._roles import ROLE_DENIED
from tests.authz.tenancy._world import World, WorldUser, snapshot_org

OWNER_REQUIRED = "Owner role required"

_ORG = "/api/v1/organizations/{a}"

# (action, actor, status, detail). Combinations that make no sense are simply absent.
MATRIX: list[tuple[str, str, int, str | None]] = [
    ("invite_member", "owner", 201, None),
    ("invite_member", "admin", 201, None),
    ("invite_member", "member", 403, ROLE_DENIED),
    ("invite_admin", "owner", 201, None),
    ("invite_admin", "admin", 403, OWNER_REQUIRED),
    ("invite_admin", "member", 403, ROLE_DENIED),
    ("invite_owner", "owner", 400, "Cannot invite as owner"),
    ("invite_owner", "admin", 400, "Cannot invite as owner"),
    ("invite_owner", "member", 403, ROLE_DENIED),
    ("update_member", "owner", 200, None),
    ("update_member", "admin", 200, None),
    ("update_member", "member", 403, ROLE_DENIED),
    ("promote_member", "owner", 200, None),
    ("promote_member", "admin", 403, OWNER_REQUIRED),
    ("promote_member", "member", 403, ROLE_DENIED),
    ("demote_admin", "owner", 200, None),
    ("demote_admin", "admin", 403, OWNER_REQUIRED),
    ("demote_admin", "member", 403, ROLE_DENIED),
    ("change_owner", "owner", 200, None),
    ("change_owner", "admin", 403, OWNER_REQUIRED),
    ("change_owner", "member", 403, ROLE_DENIED),
    ("remove_member", "owner", 204, None),
    ("remove_member", "admin", 204, None),
    ("remove_member", "member", 403, ROLE_DENIED),
    ("remove_admin", "owner", 204, None),
    ("remove_admin", "admin", 403, OWNER_REQUIRED),
    ("remove_admin", "member", 403, ROLE_DENIED),
    ("remove_owner", "owner", 204, None),
    ("remove_owner", "admin", 403, OWNER_REQUIRED),
    ("remove_owner", "member", 403, ROLE_DENIED),
    ("admin_self_demote", "admin", 403, OWNER_REQUIRED),
    ("admin_self_remove", "admin", 403, OWNER_REQUIRED),
    ("revoke_admin_invite", "owner", 204, None),
    ("revoke_admin_invite", "admin", 204, None),
    ("revoke_admin_invite", "member", 403, ROLE_DENIED),
    ("admin_on_last_owner", "admin", 403, OWNER_REQUIRED),
    ("admin_remove_last_owner", "admin", 403, OWNER_REQUIRED),
]


@pytest_asyncio.fixture
async def extra_member(
    fresh_world: World,
) -> AsyncGenerator[Callable[..., Awaitable[int]], None]:
    """Add users to A. Depends on `fresh_world`, so its teardown runs before the world drops."""
    a = fresh_world.a
    created: list[int] = []

    async def make(role: str, *, legacy_role: str | None = None) -> int:
        n = len(created) + 1
        async with AsyncSessionLocal() as session:
            user = User(
                firebase_uid=f"authz-{a.marker}-extra-{n}",
                email=f"extra{n}-{a.marker}@example.com",
                role="member",
                org_id=a.org_id,
                org_role=legacy_role or role,
                auth_provider="password",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(Membership(user_id=user.id, org_id=a.org_id, role=role, status="active"))
            await session.commit()
            created.append(user.id)
            return user.id

    yield make

    if created:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Membership).where(Membership.user_id.in_(created)))
            await session.execute(delete(User).where(User.id.in_(created)))
            await session.commit()


@pytest_asyncio.fixture
async def admin_invite(fresh_world: World) -> int:
    a = fresh_world.a
    async with AsyncSessionLocal() as session:
        invite = Invitation(
            email=f"admin-invitee-{a.marker}@example.com",
            org_id=a.org_id,
            inviter_id=a.owner.user_id,
            role="admin",
            token=uuid.uuid4().hex,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(invite)
        await session.commit()
        return invite.id


async def _member_state(org_id: int, user_id: int) -> tuple[str | None, str | None, int | None]:
    """(membership role if active, legacy org_role, legacy org_id) for one user."""
    async with AsyncSessionLocal() as session:
        role = (
            await session.execute(
                select(Membership.role).where(
                    Membership.user_id == user_id,
                    Membership.org_id == org_id,
                    Membership.status == "active",
                )
            )
        ).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        return role, user.org_role, user.org_id


async def _invite_row(email: str) -> Invitation | None:
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(select(Invitation).where(Invitation.email == email))
        ).scalar_one_or_none()


@pytest.mark.parametrize(
    ("action", "actor", "status", "detail"),
    [pytest.param(*row, id=f"{row[0]}-{row[1]}") for row in MATRIX],
)
async def test_member_role_matrix(
    action, actor, status, detail, fresh_world, as_user, extra_member, admin_invite
):
    world = fresh_world
    a = world.a
    base = _ORG.format(a=a.org_id)
    new_email = f"new-{a.marker}@example.com"
    members = f"{base}/members"

    # Owner rows that target an extra owner leave A with two owners.
    extra_admin = extra_owner = None
    if action in {"demote_admin", "remove_admin"}:
        extra_admin = await extra_member("admin")
    if action in {"change_owner", "remove_owner"}:
        extra_owner = await extra_member("owner")

    member_id = a.member.user_id
    # action -> (method, url, json body)
    requests = {
        "invite_member": ("POST", f"{base}/invites", {"email": new_email, "org_role": "member"}),
        "invite_admin": ("POST", f"{base}/invites", {"email": new_email, "org_role": "admin"}),
        "invite_owner": ("POST", f"{base}/invites", {"email": new_email, "org_role": "owner"}),
        "update_member": ("PATCH", f"{members}/{member_id}", {"org_role": "member"}),
        "promote_member": ("PATCH", f"{members}/{member_id}", {"org_role": "admin"}),
        "demote_admin": ("PATCH", f"{members}/{extra_admin}", {"org_role": "member"}),
        "change_owner": ("PATCH", f"{members}/{extra_owner}", {"org_role": "admin"}),
        "remove_member": ("DELETE", f"{members}/{member_id}", None),
        "remove_admin": ("DELETE", f"{members}/{extra_admin}", None),
        "remove_owner": ("DELETE", f"{members}/{extra_owner}", None),
        "admin_self_demote": ("PATCH", f"{members}/{a.admin.user_id}", {"org_role": "member"}),
        "admin_self_remove": ("DELETE", f"{members}/{a.admin.user_id}", None),
        "revoke_admin_invite": ("DELETE", f"{base}/invites/{admin_invite}", None),
        "admin_on_last_owner": ("PATCH", f"{members}/{a.owner.user_id}", {"org_role": "admin"}),
        "admin_remove_last_owner": ("DELETE", f"{members}/{a.owner.user_id}", None),
    }
    method, url, body = requests[action]
    client = await as_user(getattr(a, actor))
    before = await snapshot_org(a.org_id, world.upload_dir)

    resp = await client.request(method, url, json=body)

    assert resp.status_code == status, f"{resp.status_code}: {resp.text}"
    if detail is not None:
        assert resp.json()["detail"] == detail
    if status >= 400:
        assert await snapshot_org(a.org_id, world.upload_dir) == before
        return

    if action.startswith("invite_"):
        row = await _invite_row(new_email)
        assert row is not None
        assert row.role == body["org_role"]
        assert row.status == "pending"
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Invitation).where(Invitation.email == new_email))
            await session.commit()
    elif action == "revoke_admin_invite":
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(Invitation).where(Invitation.id == admin_invite))
            ).scalar_one()
            assert row.status == "revoked"
    elif method == "PATCH":
        target = int(url.rsplit("/", 1)[1])
        role, legacy_role, legacy_org = await _member_state(a.org_id, target)
        assert role == body["org_role"]
        assert legacy_org == a.org_id
        assert legacy_role == body["org_role"]
    else:
        target = int(url.rsplit("/", 1)[1])
        role, legacy_role, legacy_org = await _member_state(a.org_id, target)
        assert role is None
        assert legacy_role is None
        assert legacy_org is None


async def test_last_owner_cannot_demote_self(fresh_world, as_user):
    a = fresh_world.a
    client = await as_user(a.owner)
    before = await snapshot_org(a.org_id, fresh_world.upload_dir)

    resp = await client.patch(
        f"{_ORG.format(a=a.org_id)}/members/{a.owner.user_id}", json={"org_role": "admin"}
    )

    assert resp.status_code == 400, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Cannot demote yourself as the last organization owner"
    assert await snapshot_org(a.org_id, fresh_world.upload_dir) == before


async def test_last_owner_cannot_be_removed(fresh_world, as_user):
    a = fresh_world.a
    client = await as_user(a.owner)
    before = await snapshot_org(a.org_id, fresh_world.upload_dir)

    resp = await client.delete(f"{_ORG.format(a=a.org_id)}/members/{a.owner.user_id}")

    assert resp.status_code == 400, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Cannot remove the last organization owner"
    assert await snapshot_org(a.org_id, fresh_world.upload_dir) == before


async def test_nonstandard_target_role_is_owner_only(fresh_world, as_user, extra_member):
    # "Owner" (capitalised) in the Membership row only: it must fail closed, toward the owner.
    a = fresh_world.a
    target = await extra_member("Owner", legacy_role="member")
    client = await as_user(a.admin)
    url = f"{_ORG.format(a=a.org_id)}/members/{target}"
    before = await snapshot_org(a.org_id, fresh_world.upload_dir)

    patched = await client.patch(url, json={"org_role": "member"})
    deleted = await client.delete(url)

    for resp in (patched, deleted):
        assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == OWNER_REQUIRED
    assert await snapshot_org(a.org_id, fresh_world.upload_dir) == before


async def test_owner_rule_on_alias_routes(fresh_world, as_user, extra_member):
    a = fresh_world.a
    extra_admin = await extra_member("admin")
    client = await as_user(a.admin)
    before = await snapshot_org(a.org_id, fresh_world.upload_dir)

    put = await client.put(
        f"/api/v1/orgs/{a.org_id}/members/{a.member.user_id}", json={"org_role": "admin"}
    )
    invite = await client.post(
        f"/api/v1/orgs/{a.org_id}/invites",
        json={"email": f"alias-{a.marker}@example.com", "org_role": "admin"},
    )

    delete = await client.delete(f"/api/v1/orgs/{a.org_id}/members/{extra_admin}")

    for resp in (put, invite, delete):
        assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == OWNER_REQUIRED
    assert await snapshot_org(a.org_id, fresh_world.upload_dir) == before


# ── Re-invite after removal ───────────────────────────────────────────────────


def _extra_world_user(world: World, n: int, user_id: int) -> WorldUser:
    """The n-th user `extra_member` created, as a client-ready identity."""
    a = world.a
    return WorldUser(
        key=f"extra{n}",
        uid=f"authz-{a.marker}-extra-{n}",
        email=f"extra{n}-{a.marker}@example.com",
        user_id=user_id,
    )


async def _pending_token(email: str) -> str:
    async with AsyncSessionLocal() as session:
        invite = (
            await session.execute(
                select(Invitation).where(Invitation.email == email, Invitation.status == "pending")
            )
        ).scalar_one()
        return invite.token


async def _membership_rows(org_id: int, user_id: int) -> list[tuple[str, str]]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Membership.role, Membership.status).where(
                Membership.user_id == user_id, Membership.org_id == org_id
            )
        )
        return [(r, s) for r, s in rows.all()]


async def _remove_reinvite_accept(world: World, as_user, who: WorldUser) -> None:
    a = world.a
    owner = await as_user(a.owner)
    base = _ORG.format(a=a.org_id)
    removed = await owner.delete(f"{base}/members/{who.user_id}")
    assert removed.status_code == 204, removed.text
    invited = await owner.post(f"{base}/invites", json={"email": who.email, "org_role": "member"})
    assert invited.status_code == 201, invited.text
    token = await _pending_token(who.email)

    resp = await (await as_user(who)).post(f"/api/v1/invites/{token}/accept")

    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
    assert resp.json()["org_id"] == a.org_id
    assert await _membership_rows(a.org_id, who.user_id) == [("member", "active")]
    assert await _member_state(a.org_id, who.user_id) == ("member", "member", a.org_id)


async def test_removed_member_accepts_reinvite(fresh_world, as_user):
    await _remove_reinvite_accept(fresh_world, as_user, fresh_world.a.member)


async def test_removed_admin_reinvited_as_member_comes_back_as_member(
    fresh_world, as_user, extra_member
):
    admin_id = await extra_member("admin")
    who = _extra_world_user(fresh_world, 1, admin_id)

    await _remove_reinvite_accept(fresh_world, as_user, who)


# ── Owner and target races ────────────────────────────────────────────────────


async def test_concurrent_cross_demotion_keeps_an_owner(fresh_world, as_user, extra_member):
    a = fresh_world.a
    second = _extra_world_user(fresh_world, 1, await extra_member("owner"))
    first_client = await as_user(a.owner)
    second_client = await as_user(second)
    base = _ORG.format(a=a.org_id)

    results = await asyncio.gather(
        first_client.patch(f"{base}/members/{second.user_id}", json={"org_role": "admin"}),
        second_client.patch(f"{base}/members/{a.owner.user_id}", json={"org_role": "admin"}),
    )

    # Which refusal the loser gets depends on timing; it must be a clean 4xx, never both winning.
    assert sorted(r.status_code for r in results)[0] == 200, [r.text for r in results]
    assert all(r.status_code in {200, 400, 403} for r in results), [r.text for r in results]
    assert await _active_owner_count(a.org_id) == 1


async def _active_owner_count(org_id: int) -> int:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Membership.id).where(
                Membership.org_id == org_id,
                Membership.status == "active",
                Membership.role == "owner",
            )
        )
        return len(rows.all())


async def test_last_owner_count_is_taken_under_lock(fresh_world, as_user, extra_member):
    """Two owners; one is mid-demotion (uncommitted) when the other demotes the first."""
    a = fresh_world.a
    second = _extra_world_user(fresh_world, 1, await extra_member("owner"))
    client = await as_user(second)
    url = f"{_ORG.format(a=a.org_id)}/members/{a.owner.user_id}"

    async with AsyncSessionLocal() as other:
        await other.execute(
            update(Membership)
            .where(Membership.user_id == second.user_id, Membership.org_id == a.org_id)
            .values(role="admin")
        )
        task = asyncio.ensure_future(client.patch(url, json={"org_role": "admin"}))
        await asyncio.sleep(1.0)
        await other.commit()
    resp = await asyncio.wait_for(task, timeout=15)

    assert resp.status_code == 400, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Cannot demote the last organization owner"
    assert await _active_owner_count(a.org_id) == 1


@pytest.mark.parametrize("op", ["patch", "delete"])
async def test_target_role_is_rechecked_under_lock(fresh_world, as_user, op):
    """An owner promotes the member while an admin's request for the same member is in flight."""
    a = fresh_world.a
    url = f"{_ORG.format(a=a.org_id)}/members/{a.member.user_id}"
    admin_client = await as_user(a.admin)
    request = (
        admin_client.patch(url, json={"org_role": "member"})
        if op == "patch"
        else admin_client.delete(url)
    )

    async with AsyncSessionLocal() as other:
        await other.execute(
            update(Membership)
            .where(Membership.user_id == a.member.user_id, Membership.org_id == a.org_id)
            .values(role="admin")
        )
        task = asyncio.ensure_future(request)
        await asyncio.sleep(1.0)
        await other.commit()
    resp = await asyncio.wait_for(task, timeout=15)

    assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == OWNER_REQUIRED
    assert await _membership_rows(a.org_id, a.member.user_id) == [("admin", "active")]


async def test_role_changes_lock_target_and_owner_rows(fresh_world, as_user, extra_member):
    a = fresh_world.a
    extra_owner = await extra_member("owner")
    client = await as_user(a.owner)
    base = _ORG.format(a=a.org_id)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        patched = await client.patch(
            f"{base}/members/{a.member.user_id}", json={"org_role": "admin"}
        )
        deleted = await client.delete(f"{base}/members/{extra_owner}")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert patched.status_code == 200, patched.text
    assert deleted.status_code == 204, deleted.text
    locking = [s for s in statements if "FOR UPDATE" in s and "memberships" in s]
    assert len(locking) >= 2, locking
