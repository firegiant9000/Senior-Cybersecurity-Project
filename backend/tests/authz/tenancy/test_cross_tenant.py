"""Cross-tenant sweep: no other-org, no-org or removed caller reads or changes another org's data.

Every request is sent with a real minted token. Routes that name a target org are aimed at org A
by callers who do not belong to it; routes that take the org from the session are called as each
caller and must only ever show that caller's own organization.
"""

import pytest

from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from tests.authz.route_table import ROUTES
from tests.authz.tenancy._cases import CASES, Case, Req
from tests.authz.tenancy._world import World, WorldUser, snapshot_org

CALLERS = ("b_owner", "b_admin", "b_member", "no_org", "a_removed")

_DENIED = sorted(key for key, case in CASES.items() if case.denial is not None)
_CALLER_ROUTES = sorted(key for key, case in CASES.items() if case.denial is None)


def _caller(world: World, caller: str) -> WorldUser:
    if caller in ("no_org", "a_removed"):
        return getattr(world, caller)
    org, role = caller.split("_")
    user = getattr(world.org(org.upper()), role)
    assert user is not None
    return user


def _params(keys: list[tuple[str, str]]) -> list:
    return [
        pytest.param(key, caller, id=f"{key[0]} {key[1]}-{caller}")
        for key in keys
        for caller in CALLERS
    ]


async def _send(client, req: Req):
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )


@pytest.mark.parametrize(("key", "caller"), _params(_DENIED))
async def test_cross_tenant_denied(key, caller, world, as_user):
    case: Case = CASES[key]
    client = await as_user(_caller(world, caller))
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code in {403, 404}, f"{resp.status_code}: {resp.text}"
    if caller == "b_owner":
        assert resp.status_code == case.denial, resp.text
        assert resp.json()["detail"] == case.denial_detail
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    body = resp.text.lower()
    assert world.a.marker not in body
    for user in (world.a.owner, world.a.admin, world.a.member):
        assert user is not None
        assert user.email.lower() not in body


@pytest.mark.parametrize(("key", "caller"), _params(_CALLER_ROUTES))
async def test_caller_route_sees_only_own_org(key, caller, fresh_world, as_user):
    world = fresh_world
    case: Case = CASES[key]
    client = await as_user(_caller(world, caller))
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _send(client, case.build(world, world.b))

    if caller in ("no_org", "a_removed"):
        expected = case.allowed if case.admin_bypass else 403
    elif caller == "b_member" and ROUTES[key].min_role == "org:admin":
        expected = 403
    else:
        expected = case.allowed
    assert resp.status_code == expected, f"{resp.status_code}: {resp.text}"

    body = resp.text.lower()
    assert world.a.marker not in body
    if 200 <= resp.status_code < 300 and caller.startswith("b_"):
        if case.shows_marker:
            assert world.b.marker in body
        if case.belongs_to is not None:
            data = resp.json()
            assert case.belongs_to(data, world.b)
            assert not case.belongs_to(data, world.a)
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_agent_token_scoped_to_its_org(world, authz_client):
    async with AsyncSessionLocal() as session:
        issued = await agent_token.issue(
            SqlAgentEnrollmentRepository(session),
            org_id=world.b.org_id,
            name=f"{world.b.marker}-sweep-agent",
            scopes=["scan:upload"],
            created_by_user_id=world.b.owner.user_id,
        )
        await session.commit()
    client = await authz_client(issued.raw_token)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await client.get(f"/api/v1/inventory/scans/{world.a.ids['scan_run_id']}")

    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Scan run not found"
    assert world.a.marker not in resp.text.lower()
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before

    # Positive control: the same token reads its own org's scan run, so the 404 is not a bad path.
    own = await client.get(f"/api/v1/inventory/scans/{world.b.ids['scan_run_id']}")
    assert own.status_code == 200, own.text
