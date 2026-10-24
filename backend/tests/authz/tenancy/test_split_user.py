"""The split user (legacy org A, active membership only in B): which orgs each route reaches.

Routes that name a target org are aimed at C, A and B in turn. Routes that take the org from the
session are called once and must show only the legacy org's (A's) data.

Two kinds of assertion live here:
- Hard invariant: the split user never reaches org C, and a refused request changes nothing.
- Characterization: the exact A/B pins in `Case.split_reaches` record how the two role stores
  disagree today (T-TEN-12, tracked by the OPEN row T-TEN-14 in docs/security/threat_model.md).
  They are expected to change when the stores merge; update them then, do not treat them as intent.
"""

import pytest

from tests.authz.tenancy._cases import CASES, Case, Req
from tests.authz.tenancy._world import snapshot_org

_TARGETED = sorted(k for k, c in CASES.items() if c.denial is not None)
_CALLER = sorted(k for k, c in CASES.items() if c.denial is None)


async def _send(client, req: Req):
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )


def _ids(keys):
    return [pytest.param(k, id=f"{k[0]} {k[1]}") for k in keys]


@pytest.mark.parametrize("key", _ids(_TARGETED))
async def test_split_user_reach(key, fresh_world, as_user):
    world = fresh_world
    case: Case = CASES[key]
    client = await as_user(world.split)
    reached: dict[str, bool] = {}

    for target in ("C", "A", "B"):
        org = world.org(target)
        before = await snapshot_org(org.org_id, world.upload_dir)
        resp = await _send(client, case.build(world, org))
        detail = f"{key} -> {target}: {resp.status_code}: {resp.text}"
        if resp.status_code == case.allowed:
            reached[target] = True
        elif resp.status_code in {403, 404}:
            reached[target] = False
        else:
            prefix = "split user reached org C: severe-finding stop; " if target == "C" else ""
            pytest.fail(f"{prefix}unexpected status for {detail}")

        if target == "C":
            assert not reached["C"], "split user reached org C: severe-finding stop"
            assert world.c.marker not in resp.text.lower()
        if not reached[target]:
            assert await snapshot_org(org.org_id, world.upload_dir) == before, detail

    # Characterization of the T-TEN-14 store drift (expected to change on merge), not a hard invariant.
    assert {t for t in "AB" if reached[t]} == case.split_reaches, f"{key}: {reached}"


@pytest.mark.parametrize("key", _ids(_CALLER))
async def test_split_user_caller_route_lands_in_legacy_org(key, fresh_world, as_user):
    world = fresh_world
    case: Case = CASES[key]
    client = await as_user(world.split)
    before_b = await snapshot_org(world.b.org_id, world.upload_dir)

    # The builder ignores the target: the org comes from the session (the legacy store -> A).
    resp = await _send(client, case.build(world, world.a))

    assert resp.status_code == case.allowed, f"{resp.status_code}: {resp.text}"
    body = resp.text.lower()
    assert world.c.marker not in body
    if case.shows_marker:
        assert world.a.marker in body
        assert world.b.marker not in body
    if case.belongs_to is not None:
        data = resp.json()
        assert case.belongs_to(data, world.a)
        assert not case.belongs_to(data, world.b)
    if case.org_free:
        # No body to inspect: the split user's writes must still land in A, never in B.
        assert await snapshot_org(world.b.org_id, world.upload_dir) == before_b
