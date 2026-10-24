"""Global-admin boundary: only the pinned routes let a global admin into another org.

The admin has no org of their own and is sent at org A. Routes marked `admin_bypass` answer with
their normal status; every other route (including the members routes) must refuse and change nothing.
"""

import pytest

from tests.authz.tenancy._cases import CASES, Case, Req
from tests.authz.tenancy._world import snapshot_org


async def _send(client, req: Req):
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )


@pytest.mark.parametrize("key", [pytest.param(k, id=f"{k[0]} {k[1]}") for k in sorted(CASES)])
async def test_global_admin_boundary(key, fresh_world, as_user):
    world = fresh_world
    case: Case = CASES[key]
    client = await as_user(world.global_admin)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _send(client, case.build(world, world.a))

    if case.admin_bypass:
        assert resp.status_code == case.allowed, f"{resp.status_code}: {resp.text}"
        if case.allowed_detail is not None:
            assert resp.json()["detail"] == case.allowed_detail
    else:
        assert resp.status_code in {403, 404}, f"{resp.status_code}: {resp.text}"
        assert await snapshot_org(world.a.org_id, world.upload_dir) == before
        assert world.a.marker not in resp.text.lower()
