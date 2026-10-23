"""Revoking an agent revokes its whole rotation chain and never moves `revoked_at` later (T-TOK-08).

Rotate and revoke go through the real management routes; the agent checks use the real verifier.
The only patch is the service clock (`clock` fixture).
"""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.db.audit_log import AuditLog
from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from tests.authz.tenancy._agents import (
    ACCEPTED,
    AGENT_DENIED,
    AGENT_ROUTES,
    GRACE,
    STATUS,
    agent_request,
    frozen_now,
    issue_agent,
    load_agent,
    send,
    wait_until_blocked,
)
from tests.authz.tenancy._world import snapshot_org

ROUTE_PARAMS = [pytest.param(r, id=f"{r[0]} {r[1]}") for r in AGENT_ROUTES]


async def _assert_refused(client, route, world):
    req = agent_request(route, world.a)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await send(client, req)

    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == AGENT_DENIED
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def _assert_accepted(client, route, world):
    resp = await send(client, agent_request(route, world.a))
    assert resp.status_code == ACCEPTED[route], resp.text


async def _rotate(admin, agent_id: int) -> tuple[int, str]:
    resp = await admin.post(f"/api/v1/agents/{agent_id}/rotate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["agent"]["id"], body["raw_token"]


async def _revoke(admin, agent_id: int) -> None:
    resp = await admin.delete(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 204, resp.text


async def _newest_revoke_ids(org_id: int) -> list[int]:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.org_id == org_id, AuditLog.action == "agent.revoke")
                .order_by(AuditLog.id.desc())
                .limit(1)
            )
        ).scalar_one()
        return row.payload["revoked_ids"]


@pytest.mark.parametrize("route", ROUTE_PARAMS)
async def test_revoke_original_revokes_successor(route, world, authz_client, as_user, clock):
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s_id, s_token = await _rotate(admin, x.enrollment.id)

    await _revoke(admin, x.enrollment.id)

    await _assert_refused(await authz_client(s_token), route, world)
    await _assert_refused(await authz_client(x.raw_token), route, world)
    assert await _newest_revoke_ids(world.a.org_id) == sorted([x.enrollment.id, s_id])


async def test_revoke_original_after_grace_revokes_successor(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    _, s_token = await _rotate(admin, x.enrollment.id)
    clock(t0 + GRACE + timedelta(hours=1))

    await _revoke(admin, x.enrollment.id)

    await _assert_refused(await authz_client(s_token), STATUS, world)
    # Earlier than now, so it isn't moved.
    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_revoke_successor_revokes_predecessor_in_grace(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s_id, _ = await _rotate(admin, x.enrollment.id)
    later = t0 + timedelta(hours=1)
    clock(later)

    await _revoke(admin, s_id)

    await _assert_refused(await authz_client(x.raw_token), STATUS, world)
    assert (await load_agent(x.enrollment.id)).revoked_at == later


async def test_revoke_covers_two_rotations(world, authz_client, as_user, clock):
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s1_id, _ = await _rotate(admin, x.enrollment.id)
    s2_id, s2_token = await _rotate(admin, s1_id)

    await _revoke(admin, x.enrollment.id)

    await _assert_refused(await authz_client(s2_token), STATUS, world)
    assert (await load_agent(s2_id)).chain_root_id == x.enrollment.id


async def test_revoke_leaves_same_name_agent_alone(world, authz_client, as_user, clock):
    clock(frozen_now())
    name = f"{world.a.marker}-twin"
    first = await issue_agent(world.a, name=name)
    second = await issue_agent(world.a, name=name)
    admin = await as_user(world.a.admin)

    await _revoke(admin, first.enrollment.id)

    await _assert_refused(await authz_client(first.raw_token), STATUS, world)
    await _assert_accepted(await authz_client(second.raw_token), STATUS, world)


async def test_revoke_never_moves_revoked_at_later(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _revoke(admin, x.enrollment.id)
    clock(t0 + timedelta(hours=1))

    await _revoke(admin, x.enrollment.id)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0
    assert await _newest_revoke_ids(world.a.org_id) == []


async def test_revoke_waits_for_inflight_rotation(world, authz_client):
    """A revoke that starts while a rotation holds the chain lock must wait, then cover the successor."""
    org = world.a
    x = await issue_agent(org)
    x_id = x.enrollment.id
    session1 = AsyncSessionLocal()
    session2 = AsyncSessionLocal()
    task = None
    try:
        repo1 = SqlAgentEnrollmentRepository(session1)
        p1 = (await session1.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        await repo1._lock_chain_root(x_id)  # noqa: SLF001

        await session2.execute(text("SET LOCAL lock_timeout = '10s'"))
        p2 = (await session2.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        repo2 = SqlAgentEnrollmentRepository(session2)
        x2 = await repo2.get_by_id(x_id, org.org_id)
        assert x2 is not None
        task = asyncio.create_task(agent_token.revoke(repo2, x2))

        await wait_until_blocked(p2, blocker=p1)

        successor = await agent_token.issue(
            repo1,
            org_id=org.org_id,
            name=x2.name,
            scopes=["scan:upload"],
            created_by_user_id=org.owner.user_id,
            chain_root_id=x_id,
        )
        ids = await asyncio.wait_for(task, 10)

        assert successor.enrollment.id in ids
        await _assert_refused(await authz_client(successor.raw_token), STATUS, world)
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        try:
            await session2.rollback()
        finally:
            try:
                await session2.close()
            finally:
                try:
                    await session1.rollback()
                finally:
                    await session1.close()
