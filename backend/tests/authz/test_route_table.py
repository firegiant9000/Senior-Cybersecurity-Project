"""The route classification table must cover every route, and agree with the dependencies."""

from collections import Counter

import pytest

from app.main import app
from tests.authz._routes import check_table, enumerate_routes
from tests.authz.route_table import ROUTES, RouteSpec, build_table

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
    assert sum(Counter(s.cls for s in ROUTES.values()).values()) == len(enumerate_routes(app))
