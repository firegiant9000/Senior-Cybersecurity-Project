"""Caller-scoped summary routes report the caller's own totals, never A's, A+B or a global count.

The world seeds A with more vendors, domains and assets than B, so a count that leaked across orgs
(or summed them) would differ from B's seeded totals.

Covered: the routes whose response exposes a count that maps to a seeded table (readiness and
intake echo vendor, domain and asset totals in requirement details; the vendor anomaly list has one
item per vendor the org tracks).

Skipped as ambiguous: `/mine/loss-projection` (echoes the org's primary state, no counts),
`/mine/risk` (a score derived from industry, size and done findings, no table count) and
`/mine/validation` (issue categories and a quality score, not table counts).
"""

import pytest

from tests.authz.tenancy._world import OrgWorld, World

_MINE = "/api/v1/organizations/mine"
CALLERS = ("owner", "admin", "member")


def _requirements(body: dict) -> dict[str, str]:
    """Requirement key -> detail, from either the readiness items or the intake tiers."""
    if "items" in body:
        return {i["key"]: i["detail"] for i in body["items"]}
    return {r["key"]: r["detail"] for t in body["tiers"] for r in t["requirements"]}


def _check_requirement_counts(body: dict, org: OrgWorld) -> None:
    details = _requirements(body)
    assert details["vendors"] == f"{org.counts['vendors']} vendor(s) tracked"
    assert details["domains"] == f"{org.counts['domains']} domain(s) registered"
    # The primary domain is seeded on the org row; the rest are counted from their tables.
    assert details["identity_signal"] == (
        f"primary domain, {org.counts['domains']} domain(s), "
        f"{org.counts['vendors']} vendor(s), {org.counts['assets']} asset(s)"
    )


def _check_vendor_anomalies(body: dict, org: OrgWorld) -> None:
    assert body["has_vendors"] is True
    assert len(body["items"]) == org.counts["vendors"]
    assert all(item["vendor_name"].startswith(org.marker) for item in body["items"])


CHECKS = {
    f"{_MINE}/readiness": _check_requirement_counts,
    f"{_MINE}/intake": _check_requirement_counts,
    "/api/v1/anomalies/vendors": _check_vendor_anomalies,
}


def test_seeded_totals_differ_between_a_and_b(world: World):
    """Guard for the assertions below: equal totals would let a cross-org sum pass unnoticed."""
    for name in ("vendors", "domains", "assets"):
        assert world.a.counts[name] != world.b.counts[name]


@pytest.mark.parametrize("caller", CALLERS)
@pytest.mark.parametrize("url", sorted(CHECKS))
async def test_b_caller_sees_b_totals(url, caller, world, as_user):
    client = await as_user(getattr(world.b, caller))

    resp = await client.get(url)

    assert resp.status_code == 200, resp.text
    CHECKS[url](resp.json(), world.b)
    assert world.a.marker not in resp.text.lower()
