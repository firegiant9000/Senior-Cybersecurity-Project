"""Agent-token lifecycle end to end: the real verifier on both agent routes (T-TOK-07).

Tokens are issued by the real service against the real DB and sent to the real routes. The only
patch is the service clock (`clock` fixture); nothing else is faked.
"""

from datetime import timedelta

import pytest

from app.core.dependencies import get_agent_from_token
from app.main import app
from app.services import agent_token
from tests.authz.route_table import ROUTES
from tests.authz.tenancy._agents import (
    AGENT_ROUTES,
    GRACE,
    assert_accepted,
    assert_refused,
    frozen_now,
    issue_agent,
)

ROUTE_PARAMS = [pytest.param(r, id=f"{r[0]} {r[1]}") for r in AGENT_ROUTES]


def test_agent_routes_match_table():
    assert {k for k, s in ROUTES.items() if s.cls == "agent"} == set(AGENT_ROUTES)


def test_real_agent_verifier_in_use():
    assert get_agent_from_token not in app.dependency_overrides
    verify = agent_token.verify
    assert verify.__code__.co_filename.replace("\\", "/").endswith("app/services/agent_token.py")
    assert not hasattr(verify, "mock")


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_valid_token_accepted(route, world, authz_client):
    issued = await issue_agent(world.a)
    client = await authz_client(issued.raw_token)

    await assert_accepted(client, route, world)


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_revoked_token_rejected(route, world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    issued = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    resp = await admin.delete(f"/api/v1/agents/{issued.enrollment.id}")
    assert resp.status_code == 204, resp.text
    client = await authz_client(issued.raw_token)

    await assert_refused(client, route, world)


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_expired_token_rejected(route, world, authz_client, clock):
    t0 = frozen_now()
    issued = await issue_agent(world.a, now=t0 - timedelta(days=1), expires_at=t0)
    client = await authz_client(issued.raw_token)
    clock(t0)  # expiry is `<=`: the instant of expiry is already refused

    await assert_refused(client, route, world)


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_token_accepted_just_before_expiry(route, world, authz_client, clock):
    t0 = frozen_now()
    issued = await issue_agent(world.a, now=t0 - timedelta(days=1), expires_at=t0)
    client = await authz_client(issued.raw_token)
    clock(t0 - timedelta(seconds=1))

    await assert_accepted(client, route, world)


async def _rotated(world, as_user, clock):
    """Issue at t0, rotate through the route at t0; return (t0, predecessor token, successor token)."""
    t0 = frozen_now()
    clock(t0)
    issued = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    resp = await admin.post(f"/api/v1/agents/{issued.enrollment.id}/rotate")
    assert resp.status_code == 200, resp.text
    return t0, issued.raw_token, resp.json()["raw_token"]


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_rotated_predecessor_accepted_inside_grace(
    route, world, authz_client, as_user, clock
):
    t0, old, new = await _rotated(world, as_user, clock)
    clock(t0 + GRACE - timedelta(seconds=1))

    await assert_accepted(await authz_client(old), route, world)
    await assert_accepted(await authz_client(new), route, world)


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_rotated_predecessor_rejected_past_grace(route, world, authz_client, as_user, clock):
    t0, old, new = await _rotated(world, as_user, clock)
    clock(t0 + GRACE)

    await assert_refused(await authz_client(old), route, world)
    await assert_accepted(await authz_client(new), route, world)
