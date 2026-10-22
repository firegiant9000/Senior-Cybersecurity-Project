"""Route enumeration and dependency cross-check for the authz route table."""

from collections.abc import Callable
from typing import get_args

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Route

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import get_agent_from_token, require_role
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


def check_table(app: FastAPI, table: dict[tuple[str, str], RouteSpec]) -> list[str]:
    problems: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    admin_dep = require_role("admin")
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
        if spec.cls == "administrator" and admin_dep not in calls:
            problems.append(f"labelled administrator but require_role('admin') is absent: {label}")
    problems.extend(f"stale: {m} {p}" for (m, p) in table if (m, p) not in seen_keys)
    return problems
