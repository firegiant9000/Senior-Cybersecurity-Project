"""Route enumeration and dependency cross-check for the authz route table."""

from collections.abc import Callable
from typing import get_args

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Route

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import (
    get_agent_from_token,
    get_current_org,
    require_membership_role,
    require_org_role,
    require_role,
    require_same_org_membership,
)
from tests.authz.route_table import OrgFrom, RouteClass, RouteSpec

_IMPLICIT_METHODS = {"HEAD", "OPTIONS"}


def _is_enumerable(route: BaseRoute) -> bool:
    return isinstance(route, APIRoute | Route) and bool(getattr(route, "methods", None))


def unenumerable_routes(app: FastAPI) -> list[str]:
    """Routes the table cannot key by (method, path): mounts, hosts, websockets."""
    return [
        f"unenumerable: {type(route).__name__} {getattr(route, 'path', '')}"
        for route in app.routes
        if not _is_enumerable(route)
    ]


def enumerate_routes(app: FastAPI) -> list[tuple[str, str, BaseRoute]]:
    found: list[tuple[str, str, BaseRoute]] = []
    for route in app.routes:
        if not _is_enumerable(route):
            continue
        # Only a plain Starlette Route adds implicit HEAD (and the CORS layer handles
        # OPTIONS); an APIRoute declares exactly its methods, so every one is checked.
        skip = set() if isinstance(route, APIRoute) else _IMPLICIT_METHODS
        found.extend(
            (method, route.path, route) for method in sorted(route.methods) if method not in skip
        )
    return found


def _walk(dependant: Dependant, seen: set[Callable]) -> None:
    for sub in dependant.dependencies:
        if sub.call is not None:
            seen.add(sub.call)
        _walk(sub, seen)


def dependency_calls(route: BaseRoute) -> set[Callable]:
    if not isinstance(route, APIRoute):
        return set()
    calls: set[Callable] = set()
    _walk(route.dependant, calls)
    return calls


_ORG_PARAMS = {"org_id", "organization_id"}
_GLOBAL_ROLES = ("viewer", "member", "admin")
_ORG_ROLES = ("member", "admin", "owner")

# Administrator routes that legitimately take an org id: the data-lifecycle operations a
# global admin runs against any one organization (T-TEN-08, accepted).
ADMIN_ORG_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", "/api/v1/organizations/{org_id}"),
        ("GET", "/api/v1/organizations/{org_id}/export"),
        ("POST", "/api/v1/organizations/{org_id}/retention/run"),
    }
)


def _param_names(route: BaseRoute) -> set[str]:
    names: set[str] = set()
    if not isinstance(route, APIRoute):
        return names

    def walk(dependant: Dependant) -> None:
        names.update(p.name for p in dependant.path_params)
        names.update(p.name for p in dependant.query_params)
        for sub in dependant.dependencies:
            walk(sub)

    walk(route.dependant)
    return names


def _highest(found: list[str], order: tuple[str, ...]) -> str | None:
    return max(found, key=order.index) if found else None


def _global_role_enforced(calls: set[Callable]) -> str | None:
    """Highest require_role(X) in the tree (cached factory, so identity compare is exact)."""
    return _highest([r for r in _GLOBAL_ROLES if require_role(r) in calls], _GLOBAL_ROLES)


def _org_role_enforced(calls: set[Callable]) -> str | None:
    """Org role the dependency tree enforces; "member" for membership-only dependencies."""
    roles = [
        r for r in _ORG_ROLES if require_org_role(r) in calls or require_membership_role(r) in calls
    ]
    if roles:
        return _highest(roles, _ORG_ROLES)
    if get_current_org in calls or require_same_org_membership in calls:
        return "member"
    return None


def _check_roles(
    key: tuple[str, str], spec: RouteSpec, calls: set[Callable], params: set[str]
) -> list[str]:
    """Two-way check of min_role / org_from / in_handler against the dependency tree.

    get_current_org_optional is deliberately not an org dependency: it scopes nothing.
    A check made in the handler body (check_org_access) is invisible here, so those routes
    must say `in_handler=True`, and the marker is rejected where a dependency is visible.
    """
    global_role = _global_role_enforced(calls)
    org_role = _org_role_enforced(calls)
    org_params = params & _ORG_PARAMS
    label = f"{key[0]} {key[1]}"
    return [
        *_reverse_problems(key, spec, global_role, org_role, has_org_param=bool(org_params)),
        *_min_role_problems(label, spec, global_role, org_role),
        *_org_from_problems(label, spec, calls, has_org_param=bool(org_params)),
    ]


def _reverse_problems(
    key: tuple[str, str],
    spec: RouteSpec,
    global_role: str | None,
    org_role: str | None,
    *,
    has_org_param: bool,
) -> list[str]:
    """What the tree shows must be reflected in the class."""
    problems: list[str] = []
    label = f"{key[0]} {key[1]}"
    allow_admin_org = spec.cls == "administrator" and key in ADMIN_ORG_ROUTES
    if global_role == "admin" and spec.cls != "administrator":
        problems.append(f"require_role('admin') present but not labelled administrator: {label}")
    if (org_role is not None or has_org_param) and (
        spec.cls != "organization-scoped" and not allow_admin_org
    ):
        problems.append(f"org dependency or org id parameter but labelled {spec.cls}: {label}")
    if spec.in_handler and spec.cls != "organization-scoped":
        problems.append(f"in_handler is only meaningful for organization-scoped: {label}")
    return problems


def _min_role_problems(
    label: str, spec: RouteSpec, global_role: str | None, org_role: str | None
) -> list[str]:
    """What min_role claims must be visible in the tree."""
    problems: list[str] = []
    min_role = spec.min_role
    if spec.cls == "administrator" and min_role != "admin":
        problems.append(f"administrator must have min_role 'admin': {label}")
    if min_role in _GLOBAL_ROLES:
        if spec.cls not in {"authenticated-global", "administrator"}:
            problems.append(f"global min_role {min_role!r} on a {spec.cls} route: {label}")
        elif global_role != min_role:
            problems.append(
                f"min_role {min_role!r} but the tree enforces global role {global_role!r}: {label}"
            )
    elif min_role is None:
        if spec.cls == "authenticated-global" and global_role is not None:
            problems.append(f"min_role unset but require_role({global_role!r}) is present: {label}")
        if spec.cls == "organization-scoped" and org_role is not None:
            problems.append(f"min_role unset but org role {org_role!r} is enforced: {label}")
    elif min_role.startswith("org:"):
        problems.extend(_org_min_role_problems(label, spec, org_role))
    else:
        problems.append(f"unknown min_role {min_role!r}: {label}")
    return problems


def _org_min_role_problems(label: str, spec: RouteSpec, org_role: str | None) -> list[str]:
    min_role = spec.min_role or ""
    want = min_role.removeprefix("org:")
    if want not in _ORG_ROLES or spec.cls != "organization-scoped":
        return [f"bad org min_role {min_role!r} on a {spec.cls} route: {label}"]
    if spec.in_handler:
        if org_role is not None:
            return [f"in_handler set but a dependency enforces org role: {label}"]
        return []
    if org_role is None:
        return [f"{min_role} claimed but no org dependency is visible: {label}"]
    if org_role != want:
        return [f"{min_role} claimed but the tree enforces org:{org_role}: {label}"]
    return []


def _org_from_problems(
    label: str, spec: RouteSpec, calls: set[Callable], *, has_org_param: bool
) -> list[str]:
    problems: list[str] = []
    if spec.org_from == "path":
        if not has_org_param:
            problems.append(f"org_from 'path' but no org_id path/query parameter: {label}")
        if (
            spec.min_role is not None
            and not spec.in_handler
            and require_same_org_membership not in calls
        ):
            problems.append(f"org_from 'path' needs require_same_org_membership: {label}")
    elif spec.org_from is not None and has_org_param:
        problems.append(
            f"org_from {spec.org_from!r} but the route takes an org id parameter: {label}"
        )
    return problems


def check_table(app: FastAPI, table: dict[tuple[str, str], RouteSpec]) -> list[str]:
    problems: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    problems.extend(unenumerable_routes(app))
    known_classes = get_args(RouteClass)
    known_org_from = get_args(OrgFrom)
    for method, path, route in enumerate_routes(app):
        key = (method, path)
        seen_keys.add(key)
        spec = table.get(key)
        if spec is None:
            problems.append(f"unclassified: {method} {path}")
            continue
        label = f"{method} {path}"
        if spec.cls not in known_classes:
            problems.append(f"unknown class: {label} ({spec.cls!r})")
            continue
        if spec.org_from is not None and spec.org_from not in known_org_from:
            problems.append(f"unknown org_from: {label} ({spec.org_from!r})")
            continue
        calls = dependency_calls(route)
        has_user = get_current_user in calls
        has_agent = get_agent_from_token in calls
        if (spec.cls == "organization-scoped") != (spec.org_from is not None):
            problems.append(f"org_from must be set iff organization-scoped: {label}")
        if spec.cls == "public" and (has_user or has_agent):
            problems.append(f"labelled public but has an auth dependency: {label}")
        if spec.cls == "agent" and not (has_agent and not has_user):
            problems.append(f"labelled agent but agent auth missing or user auth present: {label}")
        if spec.cls in {"authenticated-global", "organization-scoped", "administrator"} and (
            not has_user
        ):
            problems.append(
                f"labelled {spec.cls} but get_current_user is not a dependency: {label}"
            )
        problems.extend(_check_roles(key, spec, calls, _param_names(route)))
    problems.extend(f"stale: {m} {p}" for (m, p) in table if (m, p) not in seen_keys)
    return problems
