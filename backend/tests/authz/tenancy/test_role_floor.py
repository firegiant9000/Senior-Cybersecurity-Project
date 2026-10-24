"""Role floor: destructive organization routes need an org admin; creating and editing stays member.

Every request goes through a minted token. A member is refused with a 403 and the pinned detail,
and a refused request changes nothing in the org.
"""

import pytest

from tests.authz.route_table import ROUTES
from tests.authz.tenancy._cases import CASES, Req
from tests.authz.tenancy._roles import (
    DESTRUCTIVE_ADMIN,
    DESTRUCTIVE_ORG,
    NEWLY_GATED,
    ROLE_DENIED,
    admin_only,
)
from tests.authz.tenancy._world import snapshot_org

_ADMIN_ROUTES = sorted(key for key in CASES if admin_only(key))
_MEMBER_ROUTES = sorted(key for key in CASES if not admin_only(key))


def _ids(keys) -> list:
    return [pytest.param(key, id=f"{key[0]} {key[1]}") for key in keys]


async def _send(client, req: Req):
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )


def test_destructive_list_matches_table():
    for key in DESTRUCTIVE_ORG:
        assert key in ROUTES, key
        assert ROUTES[key].cls == "organization-scoped", key
        assert ROUTES[key].min_role == "org:admin", key
    for key in DESTRUCTIVE_ADMIN:
        assert key in ROUTES, key
        assert ROUTES[key].cls == "administrator", key
    stale = [key for key, spec in ROUTES.items() if "intent org:admin" in spec.note]
    assert not stale, stale


def test_every_org_delete_is_admin_only():
    for key, spec in ROUTES.items():
        if key[0] != "DELETE":
            continue
        if spec.cls == "organization-scoped":
            assert spec.min_role in {"org:admin", "org:owner"}, key
            assert key in DESTRUCTIVE_ORG, key
        elif spec.cls == "administrator":
            assert key in DESTRUCTIVE_ADMIN, key


@pytest.mark.parametrize("key", _ids(sorted(NEWLY_GATED)))
async def test_other_org_member_hits_org_check_first(key, world, as_user):
    # The org check must refuse first, or a regression there would hide behind the role gate.
    case = CASES[key]
    client = await as_user(world.b.member)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == "Access denied"
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


@pytest.mark.parametrize("key", _ids(_ADMIN_ROUTES))
async def test_member_denied_on_admin_routes(key, world, as_user):
    case = CASES[key]
    client = await as_user(world.a.member)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == ROLE_DENIED
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


@pytest.mark.parametrize("key", _ids(_MEMBER_ROUTES))
async def test_member_allowed_on_member_routes(key, fresh_world, as_user):
    world = fresh_world
    case = CASES[key]
    client = await as_user(world.a.member)

    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code == case.allowed, f"{resp.status_code}: {resp.text}"
    if case.shows_marker:
        assert world.a.marker in resp.text.lower()


@pytest.mark.parametrize("key", _ids(sorted(CASES)))
async def test_admin_allowed(key, fresh_world, as_user):
    world = fresh_world
    case = CASES[key]
    client = await as_user(world.a.admin)

    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code == case.allowed, f"{resp.status_code}: {resp.text}"
    if case.allowed_detail is not None:
        assert resp.json()["detail"] == case.allowed_detail


async def test_global_admin_passes_role_floor(fresh_world, as_user):
    world = fresh_world
    client = await as_user(world.global_admin)
    vendor_id = world.a.ids["vendor_id"]

    resp = await client.delete(f"/api/v1/organizations/{world.a.org_id}/vendors/{vendor_id}")

    assert resp.status_code == 204, f"{resp.status_code}: {resp.text}"
