"""Role rules for the tenancy suite: which organization routes need which org role.

The per-route rule lives in `route_table.ROUTES[key].min_role`; the requests come from
`_cases.CASES[key].build`. This module only names the groups the role tests assert on.
"""

from tests.authz.route_table import ROUTES

ROLE_DENIED = "Insufficient organization role"

_V1 = "/api/v1"
_ORGS = f"{_V1}/organizations"

# Destructive routes that stage C moved from member to org admin (legacy org role).
NEWLY_GATED: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", f"{_ORGS}/{{org_id}}/vendors/{{vendor_id}}"),
        ("DELETE", f"{_ORGS}/{{org_id}}/uploads/{{upload_id}}"),
        ("DELETE", f"{_ORGS}/{{org_id}}/domains/{{domain_id}}"),
        ("POST", f"{_ORGS}/{{org_id}}/scan-runs/{{scan_run_id}}/rollback"),
        ("DELETE", f"{_V1}/assessments/{{assessment_id}}"),
        ("DELETE", f"{_V1}/integrations/m365"),
        ("POST", f"{_V1}/integrations/m365/consent"),
    }
)

# Every organization-scoped destructive route: the 7 above plus the ones already admin-level
# (agent delete and rotate, invite revoke and member removal on both aliases).
DESTRUCTIVE_ORG: frozenset[tuple[str, str]] = NEWLY_GATED | frozenset(
    {
        ("DELETE", f"{_V1}/agents/{{agent_id}}"),
        ("POST", f"{_V1}/agents/{{agent_id}}/rotate"),
        ("DELETE", f"{_ORGS}/{{org_id}}/invites/{{invite_id}}"),
        ("DELETE", f"{_V1}/orgs/{{org_id}}/invites/{{invite_id}}"),
        ("DELETE", f"{_ORGS}/{{org_id}}/members/{{user_id}}"),
        ("DELETE", f"{_V1}/orgs/{{org_id}}/members/{{user_id}}"),
    }
)

# Administrator-class (global admin) routes that delete or export an organization.
DESTRUCTIVE_ADMIN: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", f"{_ORGS}/{{org_id}}"),
        ("GET", f"{_ORGS}/{{org_id}}/export"),
        ("POST", f"{_ORGS}/{{org_id}}/retention/run"),
    }
)


def admin_only(key: tuple[str, str]) -> bool:
    return ROUTES[key].min_role in {"org:admin", "org:owner"}
