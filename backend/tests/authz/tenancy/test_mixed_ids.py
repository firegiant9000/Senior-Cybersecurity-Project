"""Mixed path/resource cases: the caller's own org in the path, another org's resource id.

The main sweep aims the path org and every resource id at the same org, so the path check refuses
the request before the repository's org filter runs. Here the path (or query) org is the caller's
own org (B) and the resource ids belong to A, so only the resource lookup can refuse. B's owner
and admin must get the pinned not-found, with A's rows and files unchanged and no A data in the body.
"""

import pytest

from tests.authz.tenancy._cases import (
    CASES,
    MIXED,
    Case,
    mixed_request,
    resource_id_keys,
)
from tests.authz.tenancy._world import snapshot_org

_KEYS = sorted(resource_id_keys())


def test_every_resource_id_route_has_a_mixed_case():
    expected = resource_id_keys()
    actual = set(MIXED)
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)
    assert expected, "no resource-id routes found: the route table changed shape"
    assert not missing and not stale, f"missing mixed cases: {missing}; stale: {stale}"
    assert expected <= set(CASES)


@pytest.mark.parametrize("caller", ["owner", "admin"])
@pytest.mark.parametrize("key", [pytest.param(k, id=f"{k[0]} {k[1]}") for k in _KEYS])
async def test_own_org_path_with_other_orgs_resource_id(key, caller, world, as_user):
    case: Case = CASES[key]
    pin = MIXED[key]
    user = getattr(world.b, caller)
    client = await as_user(user)
    before_a = await snapshot_org(world.a.org_id, world.upload_dir)
    req = mixed_request(case, world)

    resp = await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )

    assert resp.status_code == pin.status, f"{resp.status_code}: {resp.text}"
    assert resp.json()["detail"] == pin.detail
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before_a
    body = resp.text.lower()
    assert world.a.marker not in body
    for member in (world.a.owner, world.a.admin, world.a.member):
        assert member.email.lower() not in body
