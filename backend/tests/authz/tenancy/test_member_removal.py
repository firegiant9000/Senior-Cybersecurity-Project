"""Member removal revokes access in both role stores, atomically.

Every request goes through a minted token. Two stores grant org access: the `memberships` table
(membership routes) and the legacy `users.org_id/org_role` columns (the legacy-store and caller
routes). Removal has to close both in one transaction, the fallback that synthesises a membership
from the legacy fields must not apply once a membership row exists, and a user who only has legacy
access can still be removed.
"""

import importlib
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import AsyncSessionLocal
from app.db.membership import Membership
from app.db.user import User
from tests.authz.tenancy._roles import ROLE_DENIED
from tests.authz.tenancy._world import World, WorldUser

OWNER_REQUIRED = "Owner role required"
_DENIED_ORG = "Access denied for this organization"

_V1 = "/api/v1"


def _denied_probes(org_id: int) -> list[tuple[str, str]]:
    """One route per store: membership-based, legacy-store, caller-derived."""
    return [
        ("GET", f"{_V1}/organizations/{org_id}/members"),
        ("GET", f"{_V1}/organizations/{org_id}/vendors"),
        ("GET", f"{_V1}/organizations/mine/readiness"),
    ]


async def _assert_denied_everywhere(client, org_id: int) -> None:
    for method, url in _denied_probes(org_id):
        resp = await client.request(method, url)
        assert resp.status_code in {403, 404}, f"{method} {url}: {resp.status_code}: {resp.text}"


async def _assert_reaches_membership_route(client, org_id: int) -> None:
    resp = await client.get(f"{_V1}/organizations/{org_id}/members")
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"


@pytest_asyncio.fixture
async def make_user(
    fresh_world: World,
) -> AsyncGenerator[Callable[..., Awaitable[WorldUser]], None]:
    """Create users in A. Emails carry A's marker, so the world's purge sweeps them and their
    memberships (cascade)."""
    a = fresh_world.a
    n = 0

    async def make(
        name: str,
        *,
        legacy_role: str | None,
        membership: tuple[str, str] | None = None,
    ) -> WorldUser:
        nonlocal n
        n += 1
        uid = f"authz-{a.marker}-rm-{name}-{n}"
        email = f"rm-{name}-{n}-{a.marker}@example.com"
        async with AsyncSessionLocal() as session:
            user = User(
                firebase_uid=uid,
                email=email,
                role="member",
                org_id=a.org_id if legacy_role else None,
                org_role=legacy_role,
                auth_provider="password",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            if membership is not None:
                role, status = membership
                session.add(Membership(user_id=user.id, org_id=a.org_id, role=role, status=status))
            await session.commit()
            return WorldUser(key=name, uid=uid, email=email, user_id=user.id)

    yield make


async def _state(user_id: int, org_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Membership.status, Membership.role).where(
                    Membership.user_id == user_id, Membership.org_id == org_id
                )
            )
        ).all()
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        return {
            "memberships": sorted(tuple(r) for r in rows),
            "org_id": user.org_id,
            "org_role": user.org_role,
        }


def _members_url(org_id: int, user_id: int) -> str:
    return f"{_V1}/organizations/{org_id}/members/{user_id}"


# ── Real members ──────────────────────────────────────────────────────────────


async def test_removed_member_loses_access_in_both_stores(fresh_world, as_user):
    a = fresh_world.a
    member = a.member
    member_client = await as_user(member)
    await _assert_reaches_membership_route(member_client, a.org_id)

    admin_client = await as_user(a.admin)
    resp = await admin_client.delete(_members_url(a.org_id, member.user_id))
    assert resp.status_code == 204, f"{resp.status_code}: {resp.text}"

    state = await _state(member.user_id, a.org_id)
    assert state["memberships"] == [("inactive", "member")]
    assert state["org_id"] is None
    assert state["org_role"] is None
    member_client = await as_user(member)
    await _assert_denied_everywhere(member_client, a.org_id)


async def test_removal_from_other_org_keeps_legacy_org(fresh_world, as_user):
    # `split`: legacy org A, active membership only in B. Removing it from B must not clear A.
    world = fresh_world
    client = await as_user(world.b.owner)

    resp = await client.delete(_members_url(world.b.org_id, world.split.user_id))

    assert resp.status_code == 204, f"{resp.status_code}: {resp.text}"
    state = await _state(world.split.user_id, world.b.org_id)
    assert state["memberships"] == [("inactive", "admin")]
    assert state["org_id"] == world.a.org_id
    assert state["org_role"] == "admin"


async def test_failed_commit_leaves_nothing_half_applied(
    fresh_world, as_user, monkeypatch: pytest.MonkeyPatch
):
    a = fresh_world.a
    member = a.member
    before = await _state(member.user_id, a.org_id)
    assert before["memberships"] == [("active", "member")]

    original = AsyncSession.commit
    failures: list[str] = []

    async def failing_commit(self, *args, **kwargs):
        # Fail the commit that detaches the legacy fields, once. A single-transaction removal
        # carries the membership change in that same commit, so nothing can land without it.
        if not failures and any(isinstance(o, User) and o.org_id is None for o in self.dirty):
            failures.append("boom")
            raise RuntimeError("simulated commit failure")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    admin_client = await as_user(a.admin)

    try:
        resp = await admin_client.delete(_members_url(a.org_id, member.user_id))
    except RuntimeError:
        pass
    else:
        assert resp.status_code >= 500, f"{resp.status_code}: {resp.text}"

    assert failures, "the failure was never triggered"
    assert await _state(member.user_id, a.org_id) == before


async def test_inactive_membership_with_legacy_org_is_denied(fresh_world, as_user, make_user):
    # Stale state left by the old two-step removal: inactive membership, legacy org still A.
    a = fresh_world.a
    stale = await make_user("stale", legacy_role="admin", membership=("admin", "inactive"))

    client = await as_user(stale)

    resp = await client.get(f"{_V1}/organizations/{a.org_id}/members")
    assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == _DENIED_ORG


async def test_no_membership_row_still_uses_legacy_fallback(fresh_world, as_user, make_user):
    # Accounts that predate the memberships table keep working.
    legacy = await make_user("legacy", legacy_role="member")
    client = await as_user(legacy)

    await _assert_reaches_membership_route(client, fresh_world.a.org_id)


# ── Legacy-only users (no membership row at all) ──────────────────────────────


async def test_admin_removes_legacy_only_member(fresh_world, as_user, make_user):
    a = fresh_world.a
    legacy = await make_user("legacy", legacy_role="member")
    await _assert_reaches_membership_route(await as_user(legacy), a.org_id)

    admin_client = await as_user(a.admin)
    resp = await admin_client.delete(_members_url(a.org_id, legacy.user_id))

    assert resp.status_code == 204, f"{resp.status_code}: {resp.text}"
    state = await _state(legacy.user_id, a.org_id)
    assert state == {"memberships": [], "org_id": None, "org_role": None}
    await _assert_denied_everywhere(await as_user(legacy), a.org_id)


@pytest.mark.parametrize("legacy_role", ["admin", "owner"])
async def test_legacy_only_privileged_member_needs_an_owner(
    legacy_role, fresh_world, as_user, make_user
):
    a = fresh_world.a
    legacy = await make_user("legacy", legacy_role=legacy_role)
    before = await _state(legacy.user_id, a.org_id)

    admin_resp = await (await as_user(a.admin)).delete(_members_url(a.org_id, legacy.user_id))

    assert admin_resp.status_code == 403, f"{admin_resp.status_code}: {admin_resp.text}"
    assert admin_resp.json()["detail"] == OWNER_REQUIRED
    assert await _state(legacy.user_id, a.org_id) == before

    member_resp = await (await as_user(a.member)).delete(_members_url(a.org_id, legacy.user_id))
    assert member_resp.status_code == 403
    assert member_resp.json()["detail"] == ROLE_DENIED

    owner_resp = await (await as_user(a.owner)).delete(_members_url(a.org_id, legacy.user_id))
    assert owner_resp.status_code == 204, f"{owner_resp.status_code}: {owner_resp.text}"
    assert await _state(legacy.user_id, a.org_id) == {
        "memberships": [],
        "org_id": None,
        "org_role": None,
    }
    await _assert_denied_everywhere(await as_user(legacy), a.org_id)


async def test_last_legacy_owner_cannot_be_removed(fresh_world, as_user, make_user):
    a = fresh_world.a
    # A's only membership owner steps down to admin, so the legacy owner is the last owner.
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Membership).where(
                    Membership.user_id == a.owner.user_id, Membership.org_id == a.org_id
                )
            )
        ).scalar_one()
        row.role = "admin"
        await session.commit()
    legacy_owner = await make_user("legacy-owner", legacy_role="owner")
    before = await _state(legacy_owner.user_id, a.org_id)

    client = await as_user(legacy_owner)
    resp = await client.delete(_members_url(a.org_id, legacy_owner.user_id))

    assert resp.status_code == 400, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Cannot remove the last organization owner"
    assert await _state(legacy_owner.user_id, a.org_id) == before


async def test_user_with_no_access_is_still_404(fresh_world, as_user, make_user):
    a = fresh_world.a
    nobody = await make_user("nobody", legacy_role=None)
    client = await as_user(a.admin)

    resp = await client.delete(_members_url(a.org_id, nobody.user_id))

    assert resp.status_code == 404, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Member not found"


async def test_legacy_org_elsewhere_is_404_not_cleared(fresh_world, as_user, make_user):
    # A user whose legacy org is A is not removable through B's route.
    world = fresh_world
    legacy = await make_user("legacy", legacy_role="member")

    resp = await (await as_user(world.b.owner)).delete(_members_url(world.b.org_id, legacy.user_id))

    assert resp.status_code == 404, f"{resp.status_code}: {resp.text}"
    assert (await _state(legacy.user_id, world.a.org_id))["org_id"] == world.a.org_id


# ── Migration 052 ─────────────────────────────────────────────────────────────


async def test_migration_clears_only_stale_legacy_access(fresh_world, make_user):
    a = fresh_world.a
    migration = importlib.import_module(
        "app.db.versions.052_clear_legacy_access_of_removed_members"
    )

    stale = await make_user("stale", legacy_role="admin", membership=("admin", "inactive"))
    stale_other = await make_user("stale2", legacy_role="member", membership=("member", "removed"))
    active = await make_user("active", legacy_role="member", membership=("member", "active"))
    legacy_only = await make_user("legacy-only", legacy_role="admin")
    # (user_id, org_id) is unique, so "active membership" and "inactive membership" are exclusive.
    other_org = await make_user("other-org", legacy_role="member")
    async with AsyncSessionLocal() as session:
        # Inactive in B but legacy-attached to A: the legacy org has no removed row, so it stays.
        session.add(
            Membership(
                user_id=other_org.user_id,
                org_id=fresh_world.b.org_id,
                role="member",
                status="inactive",
            )
        )
        await session.commit()
    before = {
        u.key: await _state(u.user_id, a.org_id)
        for u in (stale, stale_other, active, legacy_only, other_org)
    }

    async with AsyncSessionLocal() as session:
        await session.execute(text(migration.CLEAR_STALE_LEGACY_ACCESS_SQL))
        await session.commit()

    cleared = {"org_id": None, "org_role": None}
    assert await _state(stale.user_id, a.org_id) == {**before["stale"], **cleared}
    assert await _state(stale_other.user_id, a.org_id) == {**before["stale2"], **cleared}
    for user in (active, legacy_only, other_org):
        assert await _state(user.user_id, a.org_id) == before[user.key]
