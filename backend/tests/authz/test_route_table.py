"""The route classification table must cover every route, and agree with the dependencies."""

import re
from collections import Counter
from typing import get_args

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import check_org_access
from app.db.engine import get_session
from app.db.user import User
from app.main import app
from tests.authz._routes import (
    INLINE_CHECK_ROUTES,
    NO_MEMBERSHIP_ORG_ROUTES,
    check_table,
    enumerate_routes,
)
from tests.authz.route_table import ROUTES, RouteClass, RouteSpec, build_table

ME = ("GET", "/api/v1/auth/me")


def test_every_route_classified():
    problems = check_table(app, ROUTES)
    assert problems == [], "route table problems:\n" + "\n".join(problems)


def test_cross_check_catches_mislabel():
    mislabelled = dict(ROUTES)
    mislabelled[ME] = RouteSpec("public")
    assert any("/api/v1/auth/me" in p for p in check_table(app, mislabelled))

    missing = dict(ROUTES)
    del missing[ME]
    assert "unclassified: GET /api/v1/auth/me" in check_table(app, missing)

    stale = dict(ROUTES)
    stale[("GET", "/api/v1/nope")] = RouteSpec("public")
    assert "stale: GET /api/v1/nope" in check_table(app, stale)


def _relabel(key: tuple[str, str], spec: RouteSpec) -> list[str]:
    table = dict(ROUTES)
    assert key in table, f"{key} is not in the route table"
    table[key] = spec
    label = f"{key[0]} {key[1]}"
    return [p for p in check_table(app, table) if p.endswith(label)]


ORG_ADMIN_ROUTE = ("DELETE", "/api/v1/agents/{agent_id}")  # require_org_role("admin")
ORG_MEMBER_ROUTE = ("GET", "/api/v1/organizations/mine/risk")  # get_current_org
PATH_ADMIN_ROUTE = ("GET", "/api/v1/organizations/{org_id}/invites")  # require_membership_role
PATH_MEMBER_ROUTE = ("GET", "/api/v1/organizations/{org_id}/members")  # same-org membership
HANDLER_ROUTE = ("GET", "/api/v1/organizations/{org_id}/vendors")  # check_org_access in handler
ADMIN_ROUTE = ("POST", "/api/v1/ingest/trigger")  # require_role("admin")
VIEWER_ROUTE = ("GET", "/api/v1/ingest/runs")  # require_role("viewer")


def test_org_role_mislabels_are_caught():
    member_caller = RouteSpec("organization-scoped", "org:member", org_from="caller")
    admin_caller = RouteSpec("organization-scoped", "org:admin", org_from="caller")
    assert _relabel(ORG_ADMIN_ROUTE, member_caller)
    assert _relabel(ORG_MEMBER_ROUTE, admin_caller)
    assert not _relabel(ORG_ADMIN_ROUTE, admin_caller)
    assert not _relabel(ORG_MEMBER_ROUTE, member_caller)
    member_path = RouteSpec("organization-scoped", "org:member", org_from="path")
    admin_path = RouteSpec("organization-scoped", "org:admin", org_from="path")
    assert _relabel(PATH_ADMIN_ROUTE, member_path)
    assert _relabel(PATH_MEMBER_ROUTE, admin_path)


def test_admin_route_relabelled_lower_is_caught():
    assert _relabel(ADMIN_ROUTE, RouteSpec("authenticated-global", min_role="viewer"))
    assert _relabel(ADMIN_ROUTE, RouteSpec("authenticated-global"))
    assert _relabel(VIEWER_ROUTE, RouteSpec("authenticated-global", min_role="member"))
    assert _relabel(VIEWER_ROUTE, RouteSpec("authenticated-global"))


def test_org_dependency_route_labelled_global_is_caught():
    assert _relabel(ORG_MEMBER_ROUTE, RouteSpec("authenticated-global"))
    assert _relabel(ORG_ADMIN_ROUTE, RouteSpec("authenticated-global"))
    assert _relabel(PATH_MEMBER_ROUTE, RouteSpec("authenticated-global"))
    # A bare org_id path parameter is enough, even with no org dependency.
    assert _relabel(HANDLER_ROUTE, RouteSpec("authenticated-global", min_role="viewer"))


def test_global_admin_dependency_requires_administrator_class():
    assert _relabel(ADMIN_ROUTE, RouteSpec("organization-scoped", "org:admin", org_from="path"))


def test_in_handler_marker_must_be_explicit_and_truthful():
    in_handler = RouteSpec("organization-scoped", "org:member", org_from="path", in_handler=True)
    plain = RouteSpec("organization-scoped", "org:member", org_from="path")
    assert not _relabel(HANDLER_ROUTE, in_handler)
    assert _relabel(HANDLER_ROUTE, plain), "a path-org route with no visible check needs the marker"
    assert _relabel(PATH_MEMBER_ROUTE, in_handler), "marker on a route with a visible dependency"


def _marked_app(*, handler_checks_access: bool) -> FastAPI:
    tiny = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    if handler_checks_access:

        @tiny.get("/orgs/{org_id}/x")
        async def _x(
            org_id: int,
            user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_session),
        ) -> dict[str, str]:
            await check_org_access(user, org_id, session)
            return {}

    else:

        @tiny.get("/orgs/{org_id}/x")
        async def _y(
            org_id: int,  # noqa: ARG001
            user: User = Depends(get_current_user),  # noqa: ARG001
        ) -> dict[str, str]:
            return {}

    return tiny


def test_in_handler_marker_requires_an_access_check_call():
    spec = RouteSpec("organization-scoped", "org:member", org_from="path", in_handler=True)
    key = ("GET", "/orgs/{org_id}/x")
    assert check_table(_marked_app(handler_checks_access=True), {key: spec}) == []
    problems = check_table(_marked_app(handler_checks_access=False), {key: spec})
    assert any("calls no access check" in p for p in problems), problems


def test_inline_check_allowlist_is_minimal():
    assert {
        ("GET", "/api/v1/organizations/{org_id}"),
        ("PUT", "/api/v1/organizations/{org_id}"),
    } == INLINE_CHECK_ROUTES
    for key in INLINE_CHECK_ROUTES:
        assert ROUTES[key].in_handler


def test_no_membership_org_routes_are_a_frozen_allowlist():
    unchecked = {
        k for k, s in ROUTES.items() if s.cls == "organization-scoped" and s.min_role is None
    }
    assert (
        unchecked
        == NO_MEMBERSHIP_ORG_ROUTES
        == {
            ("POST", "/api/v1/analytics/events"),
            ("POST", "/api/v1/organizations/mine/intake-preview"),
        }
    )
    for key in unchecked:
        assert re.search(r"T-[A-Z]+-\d+", ROUTES[key].note), f"{key} note must cite a threat ID"


def test_new_org_route_without_min_role_is_caught():
    no_role = RouteSpec("organization-scoped", None, org_from="path", in_handler=True)
    assert any("min_role" in p for p in _relabel(HANDLER_ROUTE, no_role))
    uncited = RouteSpec("organization-scoped", None, org_from="body", note="no ID here")
    assert any("threat ID" in p for p in _relabel(("POST", "/api/v1/analytics/events"), uncited))


def test_body_org_routes_carry_no_path_claim():
    assert ROUTES[("POST", "/api/v1/assessments/")].org_from == "body"
    # T-TEN-10 fix (S4-B): analytics binds the org to the caller, not the body.
    assert ROUTES[("POST", "/api/v1/analytics/events")].org_from == "caller"
    assert ROUTES[("POST", "/api/v1/analytics/events")].min_role is None
    assert ROUTES[("POST", "/api/v1/organizations/mine/intake-preview")].min_role is None


def test_duplicate_entry_rejected():
    entry = ("GET", "/x", RouteSpec("public"))
    with pytest.raises(ValueError, match="duplicate: GET /x"):
        build_table([entry, entry])


def test_agent_routes_are_agent_only():
    expected = {
        ("POST", "/api/v1/inventory/scans"),
        ("GET", "/api/v1/inventory/scans/{scan_run_id}"),
    }
    assert {k for k, spec in ROUTES.items() if spec.cls == "agent"} == expected


def test_route_counts_cover_all():
    counts = Counter(s.cls for s in ROUTES.values())
    assert sum(counts[c] for c in get_args(RouteClass)) == len(enumerate_routes(app))
    assert len(enumerate_routes(app)) == 129


def _tiny_app() -> FastAPI:
    tiny = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @tiny.get("/x")
    async def _x() -> dict[str, str]:
        return {}

    return tiny


def test_unknown_class_is_reported():
    tiny = _tiny_app()
    for bad in ("publc", ""):
        table = {("GET", "/x"): RouteSpec(bad)}  # type: ignore[arg-type]
        assert f"unknown class: GET /x ({bad!r})" in check_table(tiny, table)
    table = {("GET", "/x"): RouteSpec("public", org_from="somewhere")}  # type: ignore[arg-type]
    assert any(p.startswith("unknown org_from: GET /x") for p in check_table(tiny, table))
    assert check_table(tiny, {("GET", "/x"): RouteSpec("public")}) == []


def test_mount_and_websocket_are_unenumerable():
    tiny = _tiny_app()
    tiny.mount("/sub", FastAPI())

    @tiny.websocket("/ws")
    async def _ws(websocket) -> None:  # noqa: ANN001
        await websocket.close()

    problems = check_table(tiny, {("GET", "/x"): RouteSpec("public")})
    assert "unenumerable: Mount /sub" in problems
    assert "unenumerable: APIWebSocketRoute /ws" in problems


def test_explicit_head_and_options_on_api_route_are_checked():
    tiny = _tiny_app()
    tiny.add_api_route("/y", lambda: {}, methods=["GET", "HEAD", "OPTIONS"])
    problems = check_table(tiny, {("GET", "/x"): RouteSpec("public")})
    assert "unclassified: HEAD /y" in problems
    assert "unclassified: OPTIONS /y" in problems
    # A plain Starlette route keeps its implicit HEAD out of the table.
    assert not any("/docs" in p for p in check_table(app, ROUTES))
