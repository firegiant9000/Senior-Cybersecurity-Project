"""The per-route case table is complete, consistent and drives every route to its pinned outcome."""

import pytest

from tests.authz.route_table import ROUTES
from tests.authz.tenancy._cases import CASES, org_scoped_keys


def test_every_org_scoped_route_has_a_case():
    expected = org_scoped_keys()
    actual = set(CASES)
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)
    assert not missing and not stale, f"missing cases: {missing}; stale cases: {stale}"


def test_case_table_is_consistent():
    problems: list[str] = []
    for key, case in CASES.items():
        label = f"{key[0]} {key[1]}"
        if case.denial not in {403, 404, None}:
            problems.append(f"{label}: denial {case.denial}")
        if not case.split_reaches <= {"A", "B"}:
            problems.append(f"{label}: split_reaches {set(case.split_reaches)}")
        if case.denial is None and ROUTES[key].org_from != "caller":
            problems.append(f"{label}: denial=None on a non-caller route")
        if case.allowed in {401, 403, 404}:
            problems.append(f"{label}: allowed {case.allowed}")
        if (case.denial_detail is None) != (case.denial is None):
            problems.append(f"{label}: denial_detail must be set iff denial is set")
        if case.denial is None and not (case.shows_marker or case.belongs_to or case.org_free):
            problems.append(f"{label}: denial=None needs shows_marker, belongs_to or org_free")
        if not 200 <= case.allowed < 300 and not case.note:
            problems.append(f"{label}: a non-2xx allowed ({case.allowed}) needs a note")
        if case.org_free and not case.note:
            problems.append(f"{label}: org_free needs a note")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("key", sorted(CASES), ids=[f"{m} {p}" for m, p in sorted(CASES)])
async def test_target_owner_allowed(key, fresh_world, as_user):
    case = CASES[key]
    world = fresh_world
    req = case.build(world, world.a)
    client = await as_user(world.a.owner)

    resp = await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )

    assert resp.status_code == case.allowed, resp.text
    if case.allowed_detail is not None:
        assert resp.json()["detail"] == case.allowed_detail
    body = resp.text.lower()
    if case.shows_marker:
        assert world.a.marker in body
    if case.belongs_to is not None:
        assert case.belongs_to(resp.json(), world.a)
    assert world.b.marker not in body
