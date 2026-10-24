"""The route classification table must cover every route, and agree with the dependencies."""

from collections import Counter
from typing import get_args

import pytest
from fastapi import FastAPI

from app.main import app
from tests.authz._routes import check_table, enumerate_routes
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
    assert len(enumerate_routes(app)) == 128


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
