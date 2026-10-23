"""Route classification table for the authz suite.

Every route in the app must appear here with the class its handler actually enforces.
`tests/authz/test_route_table.py` fails on a route that is unclassified, stale, or whose
class disagrees with its dependency tree (see `_routes.check_table`).

Classes:
- public: no auth dependency.
- authenticated-global: any signed-in user (optionally a global role floor); no org-owned data.
- organization-scoped: reads or writes rows owned by one org. `org_from` says where the org
  comes from: the request path/query ("path"), the caller's own org ("caller"), or a looked-up
  resource ("resource"). `min_role` is the org role enforced today ("org:member" = membership only).
  The org check and `min_role` behaviour of these routes is proven by `tests/authz/tenancy/`,
  not by `check_table`.
- agent: authenticated by agent bearer token only.
- administrator: requires the global admin role.
"""

from dataclasses import dataclass
from typing import Literal

RouteClass = Literal[
    "public", "authenticated-global", "organization-scoped", "agent", "administrator"
]
OrgFrom = Literal["path", "caller", "resource"]


@dataclass(frozen=True)
class RouteSpec:
    cls: RouteClass
    min_role: str | None = (
        None  # "viewer"|"member"|"admin" (global) or "org:member"|"org:admin"|"org:owner"
    )
    org_from: OrgFrom | None = None
    flag: str | None = None
    note: str = ""


def build_table(entries: list[tuple[str, str, RouteSpec]]) -> dict[tuple[str, str], RouteSpec]:
    table: dict[tuple[str, str], RouteSpec] = {}
    for method, path, spec in entries:
        if (method, path) in table:
            raise ValueError(f"duplicate: {method} {path}")
        table[(method, path)] = spec
    return table


_M365 = "ENABLE_M365_INTEGRATION"
_V1 = "/api/v1"
_ORGS = f"{_V1}/organizations"
_MINE = f"{_ORGS}/mine"

_PUBLIC = RouteSpec("public")
_VIEWER = RouteSpec("authenticated-global", min_role="viewer")
_SIGNED_IN = RouteSpec("authenticated-global")
_ADMIN = RouteSpec("administrator", min_role="admin")
_AGENT = RouteSpec("agent")
_ORG_MEMBER_PATH = RouteSpec("organization-scoped", min_role="org:member", org_from="path")
_ORG_ADMIN_PATH = RouteSpec("organization-scoped", min_role="org:admin", org_from="path")
_T_TEN_07_NOTE = "T-TEN-07: admins manage members; admins and owners are owner-only"
_ORG_MEMBER_CALLER = RouteSpec("organization-scoped", min_role="org:member", org_from="caller")
_ORG_ADMIN_CALLER = RouteSpec("organization-scoped", min_role="org:admin", org_from="caller")
_T_TEN_05 = "T-TEN-05: destructive, org admin"
_DESTRUCTIVE_PATH = RouteSpec(
    "organization-scoped", min_role="org:admin", org_from="path", note=_T_TEN_05
)


def _m365(note: str = "", *, destructive: bool = False) -> RouteSpec:
    return RouteSpec(
        "organization-scoped",
        min_role="org:admin" if destructive else "org:member",
        org_from="path",
        flag=_M365,
        note=_T_TEN_05 if destructive else note,
    )


ROUTES: dict[tuple[str, str], RouteSpec] = build_table(
    [
        # --- app root, health, docs -------------------------------------------------
        ("GET", "/", _PUBLIC),
        ("GET", "/health", _PUBLIC),
        ("GET", f"{_V1}/health", _PUBLIC),
        ("GET", "/docs", RouteSpec("public", note="T-PLAT-08 accepted")),
        ("GET", "/docs/oauth2-redirect", RouteSpec("public", note="T-PLAT-08 accepted")),
        ("GET", "/redoc", RouteSpec("public", note="T-PLAT-08 accepted")),
        ("GET", "/openapi.json", RouteSpec("public", note="T-PLAT-08 accepted")),
        # --- auth / public data -----------------------------------------------------
        ("GET", f"{_V1}/auth/me", RouteSpec("authenticated-global", note="creates the User row")),
        ("GET", f"{_V1}/public/stats", RouteSpec("public", note="aggregate counts, rate limited")),
        ("GET", f"{_V1}/data-status", RouteSpec("public", note="static source registry")),
        # --- global feeds behind require_role("viewer") (router-level) ---------------
        ("GET", f"{_V1}/vulnerabilities/exploited", _VIEWER),
        ("GET", f"{_V1}/vulnerabilities/exploited/severity-summary", _VIEWER),
        ("GET", f"{_V1}/vulnerabilities/risk-scored/stats", _VIEWER),
        ("GET", f"{_V1}/vulnerabilities/risk-scored", _VIEWER),
        ("GET", f"{_V1}/ic3/incidents", _VIEWER),
        ("GET", f"{_V1}/ic3/filter-options", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/attack-types", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/industry-risk", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/geographic-heatmap", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/temporal-trends", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/sector-attack-matrix", _VIEWER),
        ("GET", f"{_V1}/ic3/analytics/dashboard-summary", _VIEWER),
        ("GET", f"{_V1}/nvd/cves", _VIEWER),
        ("GET", f"{_V1}/nvd/cves/{{cve_id}}", _VIEWER),
        ("GET", f"{_V1}/nvd/analytics/severity-distribution", _VIEWER),
        ("GET", f"{_V1}/nvd/analytics/timeline", _VIEWER),
        ("GET", f"{_V1}/economics/indicators", _VIEWER),
        ("GET", f"{_V1}/anomalies/ic3", _VIEWER),
        ("GET", f"{_V1}/anomalies/trends", _VIEWER),
        (
            "GET",
            f"{_V1}/anomalies/vendors",
            RouteSpec(
                "organization-scoped",
                min_role="org:member",
                org_from="caller",
                note="get_current_org; global viewer floor",
            ),
        ),
        # --- organizations: global admin ---------------------------------------------
        ("POST", f"{_ORGS}/", _ADMIN),
        ("GET", f"{_ORGS}/", _ADMIN),
        (
            "DELETE",
            f"{_ORGS}/{{org_id}}",
            RouteSpec("administrator", min_role="admin", note="T-TEN-08 accepted; audited"),
        ),
        (
            "GET",
            f"{_ORGS}/{{org_id}}/export",
            RouteSpec("administrator", min_role="admin", note="T-TEN-08 accepted; audited"),
        ),
        (
            "POST",
            f"{_ORGS}/{{org_id}}/retention/run",
            RouteSpec("administrator", min_role="admin", note="T-TEN-08 accepted"),
        ),
        # --- organizations: /mine (org from the caller) ------------------------------
        (
            "GET",
            f"{_MINE}/executive-summary",
            RouteSpec(
                "authenticated-global",
                min_role="viewer",
                note="global threat landscape, no org data",
            ),
        ),
        ("GET", f"{_MINE}/loss-projection", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/readiness", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/intake", _ORG_MEMBER_CALLER),
        (
            "POST",
            f"{_MINE}/intake-preview",
            RouteSpec(
                "organization-scoped",
                min_role="org:member",
                org_from="caller",
                note="org optional (pre-onboarding); nothing persisted",
            ),
        ),
        ("POST", f"{_MINE}/intake/skip", _ORG_MEMBER_CALLER),
        ("POST", f"{_MINE}/intake/complete", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/validation", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/risk", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/vendor-alerts", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/findings", _ORG_MEMBER_CALLER),
        ("PATCH", f"{_MINE}/findings/{{stable_key:path}}/status", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/debug", _ORG_ADMIN_CALLER),
        ("GET", f"{_MINE}/ai-summary", _ORG_MEMBER_CALLER),
        ("POST", f"{_MINE}/ai-summary/feedback", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/ai-summary/history", _ORG_ADMIN_CALLER),
        ("GET", f"{_MINE}/ai-summary/history/{{generation_id}}", _ORG_ADMIN_CALLER),
        ("GET", f"{_MINE}/findings/history", _ORG_MEMBER_CALLER),
        ("GET", f"{_MINE}/findings/history/{{snapshot_id}}", _ORG_MEMBER_CALLER),
        # --- organizations: by path id ----------------------------------------------
        (
            "GET",
            f"{_ORGS}/{{org_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:member",
                org_from="path",
                note="legacy org_id or active Membership",
            ),
        ),
        (
            "PUT",
            f"{_ORGS}/{{org_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note="global member floor; legacy org_role owner/admin",
            ),
        ),
        # --- onboarding, assessments -------------------------------------------------
        (
            "POST",
            f"{_V1}/onboarding/complete",
            RouteSpec(
                "authenticated-global", note="creates the caller's own org; 409 if already a member"
            ),
        ),
        (
            "POST",
            f"{_V1}/assessments/",
            RouteSpec(
                "organization-scoped",
                min_role="org:member",
                org_from="path",
                note="org id comes from the request body",
            ),
        ),
        ("GET", f"{_V1}/assessments/{{org_id}}", _ORG_MEMBER_PATH),
        ("GET", f"{_V1}/assessments/{{org_id}}/history", _ORG_MEMBER_PATH),
        (
            "PUT",
            f"{_V1}/assessments/{{assessment_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:member",
                org_from="resource",
                note="route loads the submission, then checks its org (T-TEN-11)",
            ),
        ),
        (
            "DELETE",
            f"{_V1}/assessments/{{assessment_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="resource",
                note=f"{_T_TEN_05}; T-TEN-11",
            ),
        ),
        # --- vendors -----------------------------------------------------------------
        ("GET", f"{_V1}/vendors/autocomplete", _SIGNED_IN),
        ("GET", f"{_V1}/vendors/suggest", _SIGNED_IN),
        ("GET", f"{_ORGS}/{{org_id}}/vendors", _ORG_MEMBER_PATH),
        ("POST", f"{_ORGS}/{{org_id}}/vendors", _ORG_MEMBER_PATH),
        ("PUT", f"{_ORGS}/{{org_id}}/vendors/{{vendor_id}}", _ORG_MEMBER_PATH),
        ("DELETE", f"{_ORGS}/{{org_id}}/vendors/{{vendor_id}}", _DESTRUCTIVE_PATH),
        ("POST", f"{_ORGS}/{{org_id}}/vendors/import/preview", _ORG_MEMBER_PATH),
        ("POST", f"{_ORGS}/{{org_id}}/vendors/import", _ORG_MEMBER_PATH),
        # --- uploads -----------------------------------------------------------------
        ("POST", f"{_ORGS}/{{org_id}}/uploads", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/uploads", _ORG_MEMBER_PATH),
        ("DELETE", f"{_ORGS}/{{org_id}}/uploads/{{upload_id}}", _DESTRUCTIVE_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/uploads/{{upload_id}}/download", _ORG_MEMBER_PATH),
        # --- inventory (human routes) ------------------------------------------------
        ("POST", f"{_ORGS}/{{org_id}}/inventory/uploads/csv/preview", _ORG_MEMBER_PATH),
        ("POST", f"{_ORGS}/{{org_id}}/inventory/uploads/csv/import", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/scan-runs", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/assets", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/findings", _ORG_MEMBER_PATH),
        (
            "PATCH",
            f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/findings/{{finding_id}}/status",
            _ORG_MEMBER_PATH,
        ),
        ("GET", f"{_ORGS}/{{org_id}}/inventory/health", _ORG_MEMBER_PATH),
        ("PUT", f"{_ORGS}/{{org_id}}/assets/{{asset_id}}/tags", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}/diff", _ORG_MEMBER_PATH),
        ("POST", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}/rollback", _DESTRUCTIVE_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/inventory/risk-summary", _ORG_MEMBER_PATH),
        # --- inventory (agent routes) ------------------------------------------------
        (
            "POST",
            f"{_V1}/inventory/scans",
            RouteSpec("agent", note="org derived from the agent token"),
        ),
        (
            "GET",
            f"{_V1}/inventory/scans/{{scan_run_id}}",
            RouteSpec("agent", note="org derived from the agent token"),
        ),
        # --- M365 integration (feature flagged; org id is a query parameter) ----------
        ("GET", f"{_V1}/integrations/m365", _m365("flag off returns a static disabled response")),
        ("POST", f"{_V1}/integrations/m365/consent", _m365(destructive=True)),
        (
            "GET",
            f"{_V1}/integrations/m365/callback",
            RouteSpec(
                "public",
                flag=_M365,
                note="OAuth redirect; org and user come from a single-use state token",
            ),
        ),
        ("POST", f"{_V1}/integrations/m365/sync", _m365()),
        ("DELETE", f"{_V1}/integrations/m365", _m365(destructive=True)),
        # --- analytics ---------------------------------------------------------------
        (
            "POST",
            f"{_V1}/analytics/events",
            RouteSpec(
                "organization-scoped",
                min_role=None,
                org_from="caller",
                note="T-TEN-10 fixed: org bound to the caller; a differing body org is refused",
            ),
        ),
        # --- domains -----------------------------------------------------------------
        ("POST", f"{_ORGS}/{{org_id}}/domains", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/domains", _ORG_MEMBER_PATH),
        ("GET", f"{_ORGS}/{{org_id}}/domains/{{domain_id}}/external-checks", _ORG_MEMBER_PATH),
        ("DELETE", f"{_ORGS}/{{org_id}}/domains/{{domain_id}}", _DESTRUCTIVE_PATH),
        # --- invites and members (both /orgs and /organizations aliases) ------------
        (
            "POST",
            f"{_ORGS}/{{org_id}}/invites",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=_T_TEN_07_NOTE,
            ),
        ),
        (
            "POST",
            f"{_V1}/orgs/{{org_id}}/invites",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=_T_TEN_07_NOTE,
            ),
        ),
        ("GET", f"{_ORGS}/{{org_id}}/invites", _ORG_ADMIN_PATH),
        ("GET", f"{_V1}/orgs/{{org_id}}/invites", _ORG_ADMIN_PATH),
        ("DELETE", f"{_ORGS}/{{org_id}}/invites/{{invite_id}}", _ORG_ADMIN_PATH),
        ("DELETE", f"{_V1}/orgs/{{org_id}}/invites/{{invite_id}}", _ORG_ADMIN_PATH),
        (
            "GET",
            f"{_V1}/invites/{{token}}",
            RouteSpec(
                "authenticated-global",
                note="invite token is the capability; caller is not yet a member",
            ),
        ),
        (
            "POST",
            f"{_V1}/invites/{{token}}/accept",
            RouteSpec("authenticated-global", note="invite token plus email match; T-AUTH-04"),
        ),
        ("GET", f"{_ORGS}/{{org_id}}/members", _ORG_MEMBER_PATH),
        ("GET", f"{_V1}/orgs/{{org_id}}/members", _ORG_MEMBER_PATH),
        (
            "PUT",
            f"{_ORGS}/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=f"T-TEN-06; {_T_TEN_07_NOTE}",
            ),
        ),
        (
            "PUT",
            f"{_V1}/orgs/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=f"T-TEN-06; {_T_TEN_07_NOTE}",
            ),
        ),
        (
            "PATCH",
            f"{_ORGS}/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=f"T-TEN-06; {_T_TEN_07_NOTE}",
            ),
        ),
        (
            "PATCH",
            f"{_V1}/orgs/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=f"T-TEN-06; {_T_TEN_07_NOTE}",
            ),
        ),
        (
            "DELETE",
            f"{_ORGS}/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=_T_TEN_07_NOTE,
            ),
        ),
        (
            "DELETE",
            f"{_V1}/orgs/{{org_id}}/members/{{user_id}}",
            RouteSpec(
                "organization-scoped",
                min_role="org:admin",
                org_from="path",
                note=_T_TEN_07_NOTE,
            ),
        ),
        # --- ingest ------------------------------------------------------------------
        (
            "GET",
            f"{_V1}/ingest/health",
            RouteSpec("public", note="for external monitors; source freshness only"),
        ),
        ("GET", f"{_V1}/ingest/freshness", _VIEWER),
        ("GET", f"{_V1}/ingest/runs", _VIEWER),
        ("POST", f"{_V1}/ingest/runs/{{run_id}}/retry", _ADMIN),
        ("POST", f"{_V1}/ingest/runs/{{run_id}}/cancel", _ADMIN),
        ("GET", f"{_V1}/ingest/schedule", _VIEWER),
        ("POST", f"{_V1}/ingest/trigger", _ADMIN),
        ("POST", f"{_V1}/ingest/cpe-backfill", _ADMIN),
        (
            "GET",
            f"{_V1}/ingest/normalization-log",
            RouteSpec("administrator", min_role="admin", note="cross-org log; admin only"),
        ),
        # --- agent enrollment management (org admin) ---------------------------------
        ("POST", f"{_V1}/agents/enroll", _ORG_ADMIN_CALLER),
        ("GET", f"{_V1}/agents", _ORG_ADMIN_CALLER),
        ("POST", f"{_V1}/agents/{{agent_id}}/rotate", _ORG_ADMIN_CALLER),
        ("DELETE", f"{_V1}/agents/{{agent_id}}", _ORG_ADMIN_CALLER),
    ]
)
