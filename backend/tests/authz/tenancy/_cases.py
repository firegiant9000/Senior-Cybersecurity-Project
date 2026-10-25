"""Per-route request builders for every organization-scoped route.

One `Case` per organization-scoped route in `route_table.ROUTES`, grouped in the same order.
`build(world, t)` returns a valid request aimed at org `t` (its id and its seeded row ids), so a
422 can never stand in for a denial. `allowed` is what the target org's owner gets; the other
fields pin what the sweeps in later tasks expect from other callers.

Pins mean:
- `denial`: status for another org's owner targeting `t` (None: a caller route with nothing to
  target, because the org comes from the session).
- `admin_bypass`: a global admin with no org of their own reaches `t`.
- `split_reaches`: orgs the split user (legacy org A, membership in B) reaches. For a case with
  `denial is None` it means whose data the split user sees on a single call, checked with
  `shows_marker` / `belongs_to`, not which target gets `allowed`: the builder ignores `t`, so
  split -> B is the same request as split -> A and returns A's data with the same status.
- `shows_marker` / `belongs_to`: an allowed response carries the target's data, so a leak shows.
  A `belongs_to` on a write route also catches a row that lands in the wrong org.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from tests.authz.route_table import ROUTES
from tests.authz.tenancy._world import ORG_STATES, OrgWorld, World, _assessment_data


@dataclass(frozen=True)
class Req:
    method: str
    url: str
    params: dict[str, str] | None = None
    json: dict | None = None
    files: dict[str, tuple[str, bytes, str]] | None = None


@dataclass(frozen=True)
class Case:
    build: Callable[[World, OrgWorld], Req]
    allowed: int  # status for the target org's owner (positive control)
    denial: Literal[403, 404] | None  # status for B's owner targeting A; None = nothing to target
    admin_bypass: bool  # global admin (no org) gets `allowed` on target A
    # Subset of {"A", "B"} the split user gets `allowed` on. When `denial is None` it instead means
    # whose data the split user sees on one call (builder ignores `t`; see module docstring).
    split_reaches: frozenset[str]
    denial_detail: str | None = None  # the B owner's exact `detail`
    allowed_detail: str | None = None  # the owner's exact `detail` for a non-2xx `allowed`
    shows_marker: bool = False  # an allowed body contains the target org's marker
    belongs_to: Callable[[dict, OrgWorld], bool] | None = None  # an allowed body is t's data
    org_free: bool = False  # response carries no org data; needs a note
    note: str = ""


_V1 = "/api/v1"
_ORGS = f"{_V1}/organizations"
_MINE = f"{_ORGS}/mine"

_A = frozenset({"A"})
_AB = frozenset({"A", "B"})

_ACCESS_DENIED = "Access denied"
_MEMBERSHIP_DENIED = "Access denied for this organization"
_T_TEN_05 = "T-TEN-05: destructive, org admin (legacy org role)"
_T_TEN_14 = "T-TEN-14: membership and legacy org disagree for the split user"


def _org(t: OrgWorld, suffix: str = "") -> str:
    return f"{_ORGS}/{t.org_id}{suffix}"


def _org_alias(t: OrgWorld, suffix: str = "") -> str:
    return f"{_V1}/orgs/{t.org_id}{suffix}"


def _csv(name: str, text: str) -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, text.encode(), "text/csv")}


def _vendor_csv(t: OrgWorld) -> dict[str, tuple[str, bytes, str]]:
    return _csv("vendors.csv", f"vendor_name\n{t.marker}-v2\n")


def _inventory_csv(t: OrgWorld) -> dict[str, tuple[str, bytes, str]]:
    return _csv("inventory.csv", f"hostname\n{t.marker}-h2\n")


def _owns_org_id(body: dict, t: OrgWorld) -> bool:
    return body["org_id"] == t.org_id


def _owns_id(body: dict, t: OrgWorld) -> bool:
    """The body is the organization itself (`OrganizationRead.id`)."""
    return body["id"] == t.org_id


def _owns_organization_id(body: dict, t: OrgWorld) -> bool:
    return body["organization_id"] == t.org_id


# --- case factories ---------------------------------------------------------------------------


def _check_access(build, allowed, **kw) -> Case:
    """Routes guarded by `check_org_access` / `_ensure_org_access`: legacy org id, admin bypass."""
    return Case(
        build,
        allowed,
        denial=403,
        denial_detail=_ACCESS_DENIED,
        admin_bypass=True,
        split_reaches=_A,
        **kw,
    )


def _membership(build, allowed, **kw) -> Case:
    """Routes guarded by `require_same_org_membership` / `require_membership_role`."""
    return Case(
        build,
        allowed,
        denial=403,
        denial_detail=_MEMBERSHIP_DENIED,
        admin_bypass=False,
        split_reaches=_AB,
        note=kw.pop("note", _T_TEN_14),
        **kw,
    )


def _caller(build, allowed, **kw) -> Case:
    """`get_current_org` routes with nothing to target: the org is the caller's own."""
    return Case(build, allowed, denial=None, admin_bypass=False, split_reaches=_A, **kw)


def _caller_id(build, allowed, detail: str, **kw) -> Case:
    """`get_current_org` routes that take a resource id: another org's id is a 404."""
    return Case(
        build,
        allowed,
        denial=404,
        denial_detail=detail,
        admin_bypass=False,
        split_reaches=_A,
        **kw,
    )


def _get(url_for: Callable[[OrgWorld], str]) -> Callable[[World, OrgWorld], Req]:
    return lambda _w, t: Req("GET", url_for(t))


def _simple(method: str, url_for: Callable[[OrgWorld], str]) -> Callable[[World, OrgWorld], Req]:
    return lambda _w, t: Req(method, url_for(t))


def _upload_body(t: OrgWorld) -> dict[str, tuple[str, bytes, str]]:
    return _csv(f"{t.marker}-new.csv", f"hostname\n{t.marker}-up\n")


def _new_invite(_w: World, t: OrgWorld, url: str) -> Req:
    return Req("POST", url, json={"email": f"new-{uuid.uuid4().hex}@example.com"})


def _member_update(method: str, *, alias: bool):
    def build(_w: World, t: OrgWorld) -> Req:
        suffix = f"/members/{t.ids['member_user_id']}"
        url = _org_alias(t, suffix) if alias else _org(t, suffix)
        return Req(method, url, json={"org_role": "member"})

    return build


CASES: dict[tuple[str, str], Case] = {
    # --- anomalies --------------------------------------------------------------------------
    ("GET", f"{_V1}/anomalies/vendors"): _caller(
        lambda _w, _t: Req("GET", f"{_V1}/anomalies/vendors"), 200, shows_marker=True
    ),
    # --- organizations: /mine (org from the caller) -----------------------------------------
    ("GET", f"{_MINE}/loss-projection"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/loss-projection"),
        200,
        belongs_to=lambda body, t: body["state"] == ORG_STATES[t.name],
        note="the seeded orgs differ only by primary state, which the projection echoes",
    ),
    ("GET", f"{_MINE}/readiness"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/readiness"), 200, shows_marker=True
    ),
    ("GET", f"{_MINE}/intake"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/intake"), 200, shows_marker=True
    ),
    ("POST", f"{_MINE}/intake-preview"): Case(
        lambda _w, _t: Req("POST", f"{_MINE}/intake-preview", json={"name": "Preview Co"}),
        200,
        denial=None,
        admin_bypass=True,
        split_reaches=_A,
        org_free=True,
        note="pure evaluation of the posted form; needs no org, so a global admin with no org passes",
    ),
    ("POST", f"{_MINE}/intake/skip"): _caller(
        lambda _w, _t: Req("POST", f"{_MINE}/intake/skip", json={"step": "domains"}),
        200,
        shows_marker=True,
    ),
    ("POST", f"{_MINE}/intake/complete"): _caller(
        lambda _w, _t: Req("POST", f"{_MINE}/intake/complete"), 200, shows_marker=True
    ),
    ("GET", f"{_MINE}/validation"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/validation"),
        200,
        shows_marker=True,
        note="the near-duplicate vendor message quotes the org's own seeded vendor names",
    ),
    ("GET", f"{_MINE}/risk"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/risk"),
        200,
        shows_marker=True,
        note="the marker comes from the seeded done finding that earns remediation credit",
    ),
    ("GET", f"{_MINE}/vendor-alerts"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/vendor-alerts"), 200, shows_marker=True
    ),
    ("GET", f"{_MINE}/findings"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/findings"), 200, belongs_to=_owns_org_id
    ),
    ("PATCH", f"{_MINE}/findings/{{stable_key:path}}/status"): _caller(
        lambda _w, _t: Req(
            "PATCH", f"{_MINE}/findings/authz-probe-key/status", json={"status": "done"}
        ),
        200,
        org_free=True,
        note="response echoes only the posted key and status; isolation is proven by the DB snapshot",
    ),
    ("GET", f"{_MINE}/debug"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/debug"),
        200,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_MINE}/ai-summary"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/ai-summary"),
        200,
        shows_marker=True,
        note="served by the template fallback; the Gemini call is stubbed",
    ),
    ("POST", f"{_MINE}/ai-summary/feedback"): _caller(
        lambda _w, _t: Req(
            "POST", f"{_MINE}/ai-summary/feedback", json={"rating": 4, "flag": "helpful"}
        ),
        201,
        org_free=True,
        note="response echoes only the posted rating and flag; isolation is proven by the DB snapshot",
    ),
    ("GET", f"{_MINE}/ai-summary/history"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/ai-summary/history"), 200, shows_marker=True
    ),
    ("GET", f"{_MINE}/ai-summary/history/{{generation_id}}"): _caller_id(
        lambda _w, t: Req("GET", f"{_MINE}/ai-summary/history/{t.ids['ai_generation_id']}"),
        200,
        "Generation not found",
        shows_marker=True,
    ),
    ("GET", f"{_MINE}/findings/history"): _caller(
        lambda _w, _t: Req("GET", f"{_MINE}/findings/history"), 200, shows_marker=True
    ),
    ("GET", f"{_MINE}/findings/history/{{snapshot_id}}"): _caller_id(
        lambda _w, t: Req("GET", f"{_MINE}/findings/history/{t.ids['snapshot_id']}"),
        200,
        "Snapshot not found",
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    # --- organizations: by path id ----------------------------------------------------------
    ("GET", f"{_ORGS}/{{org_id}}"): Case(
        _get(lambda t: _org(t)),
        200,
        denial=403,
        denial_detail=_ACCESS_DENIED,
        admin_bypass=True,
        split_reaches=_AB,
        shows_marker=True,
        belongs_to=_owns_id,
        note="legacy org id or an active membership; the split user reaches both orgs",
    ),
    ("PUT", f"{_ORGS}/{{org_id}}"): _check_access(
        lambda _w, t: Req("PUT", _org(t), json={"name": f"{t.marker} Org"}),
        200,
        shows_marker=True,
        belongs_to=_owns_id,
        note="legacy org id and legacy org role only; memberships are ignored",
    ),
    # --- assessments ------------------------------------------------------------------------
    ("POST", f"{_V1}/assessments/"): _check_access(
        lambda _w, t: Req(
            "POST",
            f"{_V1}/assessments/",
            json={
                "organization_id": t.org_id,
                "status": "Draft",
                "data": _assessment_data(t.marker),
            },
        ),
        409,
        allowed_detail="Current assessment already exists for organization",
        note="the world seeds a current submission; the 409 is raised after the org check",
    ),
    ("GET", f"{_V1}/assessments/{{org_id}}"): _check_access(
        _get(lambda t: f"{_V1}/assessments/{t.org_id}"),
        200,
        shows_marker=True,
        belongs_to=_owns_organization_id,
    ),
    ("GET", f"{_V1}/assessments/{{org_id}}/history"): _check_access(
        _get(lambda t: f"{_V1}/assessments/{t.org_id}/history"),
        200,
        shows_marker=True,
        belongs_to=_owns_organization_id,
    ),
    ("PUT", f"{_V1}/assessments/{{assessment_id}}"): _check_access(
        lambda _w, t: Req(
            "PUT",
            f"{_V1}/assessments/{t.ids['assessment_id']}",
            json={"status": "Draft", "data": _assessment_data(t.marker)},
        ),
        500,
        allowed_detail="Failed to update assessment",
        note=(
            "the route loads the submission, then checks its org; the write that follows "
            "fails with a session-transaction error on a real database, so an owner gets 500"
        ),
    ),
    ("DELETE", f"{_V1}/assessments/{{assessment_id}}"): _check_access(
        _simple("DELETE", lambda t: f"{_V1}/assessments/{t.ids['assessment_id']}"),
        500,
        allowed_detail="Failed to delete assessment",
        note=(
            f"{_T_TEN_05}; the route loads the submission, then checks its org; the write that "
            "follows fails with a session-transaction error on a real database, so an owner "
            "gets 500"
        ),
    ),
    # --- vendors ----------------------------------------------------------------------------
    ("GET", f"{_ORGS}/{{org_id}}/vendors"): _check_access(
        _get(lambda t: _org(t, "/vendors")), 200, shows_marker=True
    ),
    ("POST", f"{_ORGS}/{{org_id}}/vendors"): _check_access(
        lambda _w, t: Req(
            "POST",
            _org(t, "/vendors"),
            json={"vendor_name": f"{t.marker}-v2", "product_name": f"{t.marker}-p2"},
        ),
        201,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("PUT", f"{_ORGS}/{{org_id}}/vendors/{{vendor_id}}"): _check_access(
        lambda _w, t: Req(
            "PUT",
            _org(t, f"/vendors/{t.ids['vendor_id']}"),
            json={"vendor_name": f"{t.marker}-v3"},
        ),
        200,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("DELETE", f"{_ORGS}/{{org_id}}/vendors/{{vendor_id}}"): _check_access(
        _simple("DELETE", lambda t: _org(t, f"/vendors/{t.ids['vendor_id']}")),
        204,
        note=_T_TEN_05,
    ),
    ("POST", f"{_ORGS}/{{org_id}}/vendors/import/preview"): _check_access(
        lambda _w, t: Req("POST", _org(t, "/vendors/import/preview"), files=_vendor_csv(t)), 200
    ),
    ("POST", f"{_ORGS}/{{org_id}}/vendors/import"): _check_access(
        lambda _w, t: Req("POST", _org(t, "/vendors/import"), files=_vendor_csv(t)), 200
    ),
    # --- uploads ----------------------------------------------------------------------------
    ("POST", f"{_ORGS}/{{org_id}}/uploads"): _check_access(
        lambda _w, t: Req("POST", _org(t, "/uploads"), files=_upload_body(t)),
        201,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/uploads"): _check_access(
        _get(lambda t: _org(t, "/uploads")), 200, shows_marker=True
    ),
    ("DELETE", f"{_ORGS}/{{org_id}}/uploads/{{upload_id}}"): _check_access(
        _simple("DELETE", lambda t: _org(t, f"/uploads/{t.ids['upload_id']}")),
        204,
        note=_T_TEN_05,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/uploads/{{upload_id}}/download"): _check_access(
        _get(lambda t: _org(t, f"/uploads/{t.ids['upload_id']}/download")),
        200,
        shows_marker=True,
    ),
    # --- inventory (human routes) -----------------------------------------------------------
    ("POST", f"{_ORGS}/{{org_id}}/inventory/uploads/csv/preview"): _check_access(
        lambda _w, t: Req(
            "POST", _org(t, "/inventory/uploads/csv/preview"), files=_inventory_csv(t)
        ),
        200,
    ),
    ("POST", f"{_ORGS}/{{org_id}}/inventory/uploads/csv/import"): _check_access(
        lambda _w, t: Req(
            "POST",
            _org(t, "/inventory/uploads/csv/import"),
            params={"confirm": "true"},
            files=_inventory_csv(t),
        ),
        200,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/scan-runs"): _check_access(
        _get(lambda t: _org(t, "/scan-runs")), 200, shows_marker=True
    ),
    ("GET", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}"): _check_access(
        _get(lambda t: _org(t, f"/scan-runs/{t.ids['scan_run_id']}")),
        200,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/assets"): _check_access(
        _get(lambda t: _org(t, "/assets")), 200, shows_marker=True
    ),
    ("GET", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}"): _check_access(
        _get(lambda t: _org(t, f"/assets/{t.ids['asset_id']}")), 200, shows_marker=True
    ),
    ("GET", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/findings"): _check_access(
        _get(lambda t: _org(t, f"/assets/{t.ids['asset_id']}/findings")), 200, shows_marker=True
    ),
    (
        "PATCH",
        f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/findings/{{finding_id}}/status",
    ): _check_access(
        lambda _w, t: Req(
            "PATCH",
            _org(t, f"/assets/{t.ids['asset_id']}/findings/{t.ids['finding_id']}/status"),
            json={"status": "accepted_risk"},
        ),
        200,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/inventory/health"): _check_access(
        _get(lambda t: _org(t, "/inventory/health")), 200, shows_marker=True
    ),
    ("PUT", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/tags"): _check_access(
        lambda _w, t: Req(
            "PUT", _org(t, f"/assets/{t.ids['asset_id']}/tags"), json={"tags": [t.marker]}
        ),
        200,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}/diff"): _check_access(
        _get(lambda t: _org(t, f"/scan-runs/{t.ids['scan_run_id']}/diff")), 200
    ),
    ("POST", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}/rollback"): _check_access(
        _simple("POST", lambda t: _org(t, f"/scan-runs/{t.ids['scan_run_id']}/rollback")),
        200,
        note=_T_TEN_05,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/inventory/risk-summary"): _check_access(
        _get(lambda t: _org(t, "/inventory/risk-summary")), 200, shows_marker=True
    ),
    # --- M365 integration (feature flagged; org id is a query parameter) --------------------
    ("GET", f"{_V1}/integrations/m365"): _check_access(
        lambda _w, t: Req("GET", f"{_V1}/integrations/m365", params={"org_id": str(t.org_id)}),
        200,
        shows_marker=True,
    ),
    ("POST", f"{_V1}/integrations/m365/consent"): _check_access(
        lambda _w, t: Req(
            "POST", f"{_V1}/integrations/m365/consent", params={"org_id": str(t.org_id)}
        ),
        200,
    ),
    ("POST", f"{_V1}/integrations/m365/sync"): _check_access(
        lambda _w, t: Req(
            "POST", f"{_V1}/integrations/m365/sync", params={"org_id": str(t.org_id)}
        ),
        200,
        note="the Graph calls are stubbed; the stored refresh token is real",
    ),
    ("DELETE", f"{_V1}/integrations/m365"): _check_access(
        lambda _w, t: Req("DELETE", f"{_V1}/integrations/m365", params={"org_id": str(t.org_id)}),
        204,
        note=_T_TEN_05,
    ),
    # --- analytics --------------------------------------------------------------------------
    ("POST", f"{_V1}/analytics/events"): Case(
        lambda _w, t: Req(
            "POST",
            f"{_V1}/analytics/events",
            json={"event_type": "dashboard_first_view", "org_id": t.org_id},
        ),
        200,
        denial=403,
        denial_detail=_ACCESS_DENIED,
        admin_bypass=False,
        split_reaches=_A,
        note="T-TEN-10 fixed: a body org that differs from the caller's own org is refused",
    ),
    # --- domains ----------------------------------------------------------------------------
    ("POST", f"{_ORGS}/{{org_id}}/domains"): _check_access(
        lambda _w, t: Req(
            "POST", _org(t, "/domains"), json={"domain_name": f"new.{t.marker}.example.com"}
        ),
        201,
        shows_marker=True,
        belongs_to=_owns_org_id,
    ),
    ("GET", f"{_ORGS}/{{org_id}}/domains"): _check_access(
        _get(lambda t: _org(t, "/domains")), 200, shows_marker=True
    ),
    ("GET", f"{_ORGS}/{{org_id}}/domains/{{domain_id}}/external-checks"): _check_access(
        _get(lambda t: _org(t, f"/domains/{t.ids['domain_id']}/external-checks")),
        200,
        shows_marker=True,
        note="the upstream lookups are stubbed",
    ),
    ("DELETE", f"{_ORGS}/{{org_id}}/domains/{{domain_id}}"): _check_access(
        _simple("DELETE", lambda t: _org(t, f"/domains/{t.ids['domain_id']}")),
        204,
        note=_T_TEN_05,
    ),
    # --- invites and members (both /organizations and /orgs aliases) ------------------------
    ("POST", f"{_ORGS}/{{org_id}}/invites"): _membership(
        lambda w, t: _new_invite(w, t, _org(t, "/invites")),
        201,
        belongs_to=_owns_org_id,
        note=f"T-TEN-07; {_T_TEN_14}",
    ),
    ("POST", f"{_V1}/orgs/{{org_id}}/invites"): _membership(
        lambda w, t: _new_invite(w, t, _org_alias(t, "/invites")),
        201,
        belongs_to=_owns_org_id,
        note=f"T-TEN-07; {_T_TEN_14}",
    ),
    ("GET", f"{_ORGS}/{{org_id}}/invites"): _membership(
        _get(lambda t: _org(t, "/invites")), 200, shows_marker=True
    ),
    ("GET", f"{_V1}/orgs/{{org_id}}/invites"): _membership(
        _get(lambda t: _org_alias(t, "/invites")), 200, shows_marker=True
    ),
    ("DELETE", f"{_ORGS}/{{org_id}}/invites/{{invite_id}}"): _membership(
        _simple("DELETE", lambda t: _org(t, f"/invites/{t.ids['invite_id']}")), 204
    ),
    ("DELETE", f"{_V1}/orgs/{{org_id}}/invites/{{invite_id}}"): _membership(
        _simple("DELETE", lambda t: _org_alias(t, f"/invites/{t.ids['invite_id']}")), 204
    ),
    ("GET", f"{_ORGS}/{{org_id}}/members"): _membership(
        _get(lambda t: _org(t, "/members")), 200, shows_marker=True
    ),
    ("GET", f"{_V1}/orgs/{{org_id}}/members"): _membership(
        _get(lambda t: _org_alias(t, "/members")), 200, shows_marker=True
    ),
    ("PUT", f"{_ORGS}/{{org_id}}/members/{{user_id}}"): _membership(
        _member_update("PUT", alias=False),
        200,
        shows_marker=True,
        note=f"T-TEN-06, T-TEN-07; {_T_TEN_14}",
    ),
    ("PUT", f"{_V1}/orgs/{{org_id}}/members/{{user_id}}"): _membership(
        _member_update("PUT", alias=True),
        200,
        shows_marker=True,
        note=f"T-TEN-06, T-TEN-07; {_T_TEN_14}",
    ),
    ("PATCH", f"{_ORGS}/{{org_id}}/members/{{user_id}}"): _membership(
        _member_update("PATCH", alias=False),
        200,
        shows_marker=True,
        note=f"T-TEN-06, T-TEN-07; {_T_TEN_14}",
    ),
    ("PATCH", f"{_V1}/orgs/{{org_id}}/members/{{user_id}}"): _membership(
        _member_update("PATCH", alias=True),
        200,
        shows_marker=True,
        note=f"T-TEN-06, T-TEN-07; {_T_TEN_14}",
    ),
    ("DELETE", f"{_ORGS}/{{org_id}}/members/{{user_id}}"): _membership(
        _simple("DELETE", lambda t: _org(t, f"/members/{t.ids['member_user_id']}")), 204
    ),
    ("DELETE", f"{_V1}/orgs/{{org_id}}/members/{{user_id}}"): _membership(
        _simple("DELETE", lambda t: _org_alias(t, f"/members/{t.ids['member_user_id']}")), 204
    ),
    # --- agent enrollment management (org admin) --------------------------------------------
    ("POST", f"{_V1}/agents/enroll"): _caller(
        lambda _w, _t: Req("POST", f"{_V1}/agents/enroll", json={"name": "authz-probe-agent"}),
        201,
        belongs_to=lambda body, t: body["agent"]["org_id"] == t.org_id,
    ),
    ("GET", f"{_V1}/agents"): _caller(
        lambda _w, _t: Req("GET", f"{_V1}/agents"), 200, shows_marker=True
    ),
    ("POST", f"{_V1}/agents/{{agent_id}}/rotate"): _caller_id(
        lambda _w, t: Req("POST", f"{_V1}/agents/{t.ids['agent_id']}/rotate"),
        200,
        "Agent not found",
        belongs_to=lambda body, t: body["agent"]["org_id"] == t.org_id,
    ),
    ("DELETE", f"{_V1}/agents/{{agent_id}}"): _caller_id(
        lambda _w, t: Req("DELETE", f"{_V1}/agents/{t.ids['agent_id']}"), 204, "Agent not found"
    ),
}


def org_scoped_keys() -> set[tuple[str, str]]:
    return {key for key, spec in ROUTES.items() if spec.cls == "organization-scoped"}


# --- mixed path/resource cases ----------------------------------------------------------------
# A route that names its org in the path AND takes a resource id has two checks: the path org and
# the repository's org filter. Aiming both at A only proves the first. The mixed request names the
# caller's own org (B) in the path and uses A's resource ids, so only the repository filter can
# refuse it.

_PLACEHOLDER = re.compile(r"\{(\w+)(?::\w+)?\}")


def resource_id_keys() -> set[tuple[str, str]]:
    """Org-scoped routes whose org comes from the path and that also take a resource id."""
    return {
        key
        for key, spec in ROUTES.items()
        if spec.cls == "organization-scoped"
        and spec.org_from == "path"
        and set(_PLACEHOLDER.findall(key[1])) - {"org_id"}
    }


@dataclass(frozen=True)
class Mixed:
    status: int  # what B's owner and admin get for A's resource id under B's own org
    detail: str  # the exact `detail`


def mixed_request(case: Case, world: World) -> Req:
    """Path/query org is B; every resource id is A's."""
    hybrid = replace(world.b, ids=world.a.ids, ids_all=world.a.ids_all)
    return case.build(world, hybrid)


def _not_found(detail: str) -> Mixed:
    return Mixed(404, detail)


# Pinned from the routes' own not-found responses: the resource lookup is filtered by the path org.
_MIXED_DETAILS: dict[str, str] = {
    "/vendors/{vendor_id}": "Vendor not found",
    "/uploads/{upload_id}": "Upload not found",
    "/scan-runs/{scan_run_id}": "Scan run not found",
    "/assets/{asset_id}": "Asset not found",
    "/domains/{domain_id}": "Domain not found",
    "/invites/{invite_id}": "Invite not found or already used",
    "/members/{user_id}": "Member not found",
}
# Longest marker first, so `/assets/{asset_id}/findings/{finding_id}/status` is matched as a
# finding, not an asset.
_MIXED_OVERRIDES: dict[str, str] = {"/findings/{finding_id}/status": "Finding not found"}


def _mixed_for(path: str) -> Mixed:
    for marker, detail in _MIXED_OVERRIDES.items():
        if marker in path:
            return _not_found(detail)
    for marker, detail in _MIXED_DETAILS.items():
        if marker in path:
            return _not_found(detail)
    raise KeyError(f"no mixed-case pin for {path}")


MIXED: dict[tuple[str, str], Mixed] = {key: _mixed_for(key[1]) for key in resource_id_keys()}
