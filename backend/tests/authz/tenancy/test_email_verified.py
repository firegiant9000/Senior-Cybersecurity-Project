"""T-AUTH-04: a verified email is required to create an account or accept an invite.

Real token verification throughout. Only the two first-contact paths are gated: an existing bound
user with an unverified token still signs in. Rows these tests create carry a uuid and are deleted
in teardown, before the world is dropped.
"""

import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.engine import AsyncSessionLocal
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.user import User
from tests.authz._issuer import mint_id_token
from tests.authz.tenancy._world import World, snapshot_org

NOT_VERIFIED = "Email address not verified"
MISMATCH = "Signed-in email does not match this account"
LINK_REFUSED = "Unable to link this sign-in to an existing account"
ME = "/api/v1/auth/me"


async def _delete_users(uid: str, email: str) -> None:
    async with AsyncSessionLocal() as session:
        ids = (
            (
                await session.execute(
                    select(User.id).where((User.firebase_uid == uid) | (User.email == email))
                )
            )
            .scalars()
            .all()
        )
        await session.execute(delete(Membership).where(Membership.user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids)))
        await session.commit()


async def _users_matching(uid: str, email: str) -> list[User]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(User).where((User.firebase_uid == uid) | (User.email == email))
        )
        return list(rows.scalars())


@pytest_asyncio.fixture
async def identity() -> AsyncGenerator[SimpleNamespace, None]:
    tag = uuid.uuid4().hex
    ident = SimpleNamespace(uid=f"verif-{tag}", email=f"verif-{tag}@example.com")
    try:
        yield ident
    finally:
        await _delete_users(ident.uid, ident.email)


@pytest_asyncio.fixture
async def invitee(fresh_world: World) -> AsyncGenerator[SimpleNamespace, None]:
    """A bound user whose stored email is A's seeded invite email."""
    async with AsyncSessionLocal() as session:
        invite = await session.get(Invitation, fresh_world.a.ids["invite_id"])
        email = invite.email
        role = invite.role
        token = invite.token
    uid = f"verif-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as session:
        user = User(firebase_uid=uid, email=email, role="viewer", auth_provider="password")
        session.add(user)
        await session.commit()
        user_id = user.id
    try:
        yield SimpleNamespace(uid=uid, email=email, user_id=user_id, role=role, token=token)
    finally:
        await _delete_users(uid, email)


async def _memberships(user_id: int) -> list[Membership]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(Membership).where(Membership.user_id == user_id))
        return list(rows.scalars())


async def _invite_status(world: World) -> str:
    async with AsyncSessionLocal() as session:
        invite = await session.get(Invitation, world.a.ids["invite_id"])
        return invite.status


def _accept_path(invitee: SimpleNamespace) -> str:
    return f"/api/v1/invites/{invitee.token}/accept"


async def _refused_create(authz_client, signing_key, identity, **mint_kwargs):
    token = mint_id_token(signing_key, uid=identity.uid, email=identity.email, **mint_kwargs)
    client = await authz_client(token)
    resp = await client.get(ME)
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == NOT_VERIFIED
    assert "WWW-Authenticate" not in resp.headers
    assert await _users_matching(identity.uid, identity.email) == []


async def test_auto_create_refused_when_unverified(accounts, signing_key, authz_client, identity):
    accounts.add(identity.uid, identity.email, email_verified=False)
    await _refused_create(authz_client, signing_key, identity, email_verified=False)


async def test_auto_create_refused_when_claim_missing(
    accounts, signing_key, authz_client, identity
):
    accounts.add(identity.uid, identity.email, email_verified=False)
    await _refused_create(authz_client, signing_key, identity, drop_claims=("email_verified",))


async def test_auto_create_refused_when_claim_is_string(
    accounts, signing_key, authz_client, identity
):
    accounts.add(identity.uid, identity.email, email_verified=False)
    await _refused_create(authz_client, signing_key, identity, extra={"email_verified": "true"})


async def test_auto_create_allowed_when_verified(accounts, signing_key, authz_client, identity):
    accounts.add(identity.uid, identity.email)
    token = mint_id_token(signing_key, uid=identity.uid, email=identity.email)
    resp = await (await authz_client(token)).get(ME)
    assert resp.status_code == 200, resp.text
    rows = await _users_matching(identity.uid, identity.email)
    assert len(rows) == 1
    assert rows[0].firebase_uid == identity.uid
    assert rows[0].role == "viewer"


async def test_link_by_email_refused_when_unverified(accounts, signing_key, authz_client, identity):
    async with AsyncSessionLocal() as session:
        session.add(User(firebase_uid=None, email=identity.email, role="viewer"))
        await session.commit()
    accounts.add(identity.uid, identity.email, email_verified=False)
    token = mint_id_token(signing_key, uid=identity.uid, email=identity.email, email_verified=False)
    resp = await (await authz_client(token)).get(ME)
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == LINK_REFUSED
    assert "WWW-Authenticate" not in resp.headers
    rows = await _users_matching(identity.uid, identity.email)
    assert len(rows) == 1
    assert rows[0].firebase_uid is None


async def test_existing_user_unverified_still_signs_in(
    fresh_world: World, accounts, signing_key, authz_client
):
    member = fresh_world.a.member
    accounts.add(member.uid, member.email, email_verified=False)
    token = mint_id_token(signing_key, uid=member.uid, email=member.email, email_verified=False)
    resp = await (await authz_client(token)).get(ME)
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == member.email


async def test_accept_invite_refused_when_unverified(
    fresh_world: World, accounts, signing_key, authz_client, invitee
):
    accounts.add(invitee.uid, invitee.email, email_verified=False)
    token = mint_id_token(signing_key, uid=invitee.uid, email=invitee.email, email_verified=False)
    before = await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir)
    resp = await (await authz_client(token)).post(_accept_path(invitee))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == NOT_VERIFIED
    assert "WWW-Authenticate" not in resp.headers
    assert await _invite_status(fresh_world) == "pending"
    assert await _memberships(invitee.user_id) == []
    assert await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir) == before


async def test_accept_invite_refused_when_token_email_differs(
    fresh_world: World, accounts, signing_key, authz_client, invitee
):
    other = f"other-{uuid.uuid4().hex}@example.com"
    accounts.add(invitee.uid, other)
    token = mint_id_token(signing_key, uid=invitee.uid, email=other)
    before = await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir)
    resp = await (await authz_client(token)).post(_accept_path(invitee))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == MISMATCH
    assert "WWW-Authenticate" not in resp.headers
    assert await _invite_status(fresh_world) == "pending"
    assert await _memberships(invitee.user_id) == []
    assert await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir) == before


async def test_accept_invite_allowed_when_verified(
    fresh_world: World, accounts, signing_key, authz_client, invitee
):
    accounts.add(invitee.uid, invitee.email)
    token = mint_id_token(signing_key, uid=invitee.uid, email=invitee.email)
    resp = await (await authz_client(token)).post(_accept_path(invitee))
    assert resp.status_code == 200, resp.text
    assert resp.json()["org_id"] == fresh_world.a.org_id
    memberships = await _memberships(invitee.user_id)
    assert [(m.org_id, m.role, m.status) for m in memberships] == [
        (fresh_world.a.org_id, invitee.role, "active")
    ]


@pytest.mark.parametrize("claim", [None, "true"])
async def test_accept_invite_refused_when_claim_not_boolean(
    fresh_world: World, accounts, signing_key, authz_client, invitee, claim
):
    accounts.add(invitee.uid, invitee.email, email_verified=False)
    kwargs = (
        {"drop_claims": ("email_verified",)}
        if claim is None
        else {"extra": {"email_verified": claim}}
    )
    token = mint_id_token(signing_key, uid=invitee.uid, email=invitee.email, **kwargs)
    before = await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir)
    resp = await (await authz_client(token)).post(_accept_path(invitee))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == NOT_VERIFIED
    assert "WWW-Authenticate" not in resp.headers
    assert await _invite_status(fresh_world) == "pending"
    assert await _memberships(invitee.user_id) == []
    assert await snapshot_org(fresh_world.a.org_id, fresh_world.upload_dir) == before
