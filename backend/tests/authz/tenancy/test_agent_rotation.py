"""Rotation acts only on active agents (T-ENR-04).

Refusals go through the real management route; the stale-object, concurrent and mid-chain tests
drive the service and repository against the real DB with separate sessions. The only patch is the
service clock (`clock` fixture).
"""

import asyncio
from datetime import timedelta

from sqlalchemy import select, text

from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from app.services.agent_token import AgentNotActiveError, IssuedToken
from tests.authz.tenancy._agents import (
    GRACE,
    NOT_ACTIVE,
    STATUS,
    assert_refused,
    frozen_now,
    issue_agent,
    load_agent,
    wait_until_blocked,
)
from tests.authz.tenancy._world import snapshot_org


async def _rotate_ok(admin, agent_id: int) -> tuple[int, str]:
    resp = await admin.post(f"/api/v1/agents/{agent_id}/rotate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["agent"]["id"], body["raw_token"]


async def _assert_rotation_refused(admin, agent_id: int, world) -> None:
    """Exactly 409 with the not-active detail, and nothing in the org changes (no new row)."""
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await admin.post(f"/api/v1/agents/{agent_id}/rotate")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == NOT_ACTIVE
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def _successor_ids(root_id: int) -> list[int]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(AgentEnrollment.id)
            .where(AgentEnrollment.chain_root_id == root_id)
            .order_by(AgentEnrollment.id)
        )
        return list(rows.scalars())


async def test_rotate_refused_when_revoked(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    resp = await admin.delete(f"/api/v1/agents/{x.enrollment.id}")
    assert resp.status_code == 204, resp.text

    await _assert_rotation_refused(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0
    await assert_refused(await authz_client(x.raw_token), STATUS, world)


async def test_rotate_refused_when_expired(world, authz_client, as_user, clock):
    t0 = frozen_now()
    x = await issue_agent(world.a, now=t0 - timedelta(days=1), expires_at=t0)
    clock(t0)
    admin = await as_user(world.a.admin)

    await _assert_rotation_refused(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at is None
    await assert_refused(await authz_client(x.raw_token), STATUS, world)


async def test_rotate_refused_during_grace(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate_ok(admin, x.enrollment.id)

    await _assert_rotation_refused(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE
    assert len(await _successor_ids(x.enrollment.id)) == 1
    # The window was not extended: the predecessor still dies at the original instant.
    clock(t0 + GRACE)
    await assert_refused(await authz_client(x.raw_token), STATUS, world)


async def test_rotate_successor_allowed(world, as_user, clock):
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s1_id, _ = await _rotate_ok(admin, x.enrollment.id)

    s2_id, _ = await _rotate_ok(admin, s1_id)

    assert (await load_agent(s2_id)).chain_root_id == x.enrollment.id


async def test_rotate_stale_agent_allowed(world, as_user, clock):
    t0 = frozen_now()
    x = await issue_agent(world.a)
    async with AsyncSessionLocal() as session:
        row = await session.get(AgentEnrollment, x.enrollment.id)
        assert row is not None
        row.last_used_at = t0 - timedelta(days=45)  # idle: status "stale", still active
        await session.commit()
    clock(t0)
    admin = await as_user(world.a.admin)

    await _rotate_ok(admin, x.enrollment.id)


async def test_stale_object_rotation_refused_by_database(world):
    """Both sessions hold X as active; only the conditional UPDATE can refuse the second."""
    org = world.a
    x = await issue_agent(org)
    now = frozen_now()
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        repo1 = SqlAgentEnrollmentRepository(session1)
        repo2 = SqlAgentEnrollmentRepository(session2)
        x1 = await repo1.get_by_id(x.enrollment.id, org.org_id)
        x2 = await repo2.get_by_id(x.enrollment.id, org.org_id)
        assert x1 is not None and x2 is not None

        first = await agent_token.rotate(repo1, x1, created_by_user_id=org.owner.user_id, now=now)
        assert isinstance(first, IssuedToken)
        try:
            await agent_token.rotate(repo2, x2, created_by_user_id=org.owner.user_id, now=now)
        except AgentNotActiveError:
            pass
        else:
            raise AssertionError("the stale object was rotated")

    assert await _successor_ids(x.enrollment.id) == [first.enrollment.id]
    assert (await load_agent(x.enrollment.id)).revoked_at == now + GRACE


async def test_rotation_after_revoke_refused_by_database(world):
    org = world.a
    x = await issue_agent(org)
    now = frozen_now()
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        repo1 = SqlAgentEnrollmentRepository(session1)
        repo2 = SqlAgentEnrollmentRepository(session2)
        x1 = await repo1.get_by_id(x.enrollment.id, org.org_id)
        x2 = await repo2.get_by_id(x.enrollment.id, org.org_id)
        assert x1 is not None and x2 is not None

        await agent_token.revoke(repo2, x2, now=now)
        try:
            await agent_token.rotate(repo1, x1, created_by_user_id=org.owner.user_id, now=now)
        except AgentNotActiveError:
            pass
        else:
            raise AssertionError("the revoked agent was rotated")

    assert await _successor_ids(x.enrollment.id) == []
    assert (await load_agent(x.enrollment.id)).revoked_at == now


async def test_concurrent_rotations_one_wins(world):
    org = world.a
    x = await issue_agent(org)
    now = frozen_now()
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        repo1 = SqlAgentEnrollmentRepository(session1)
        repo2 = SqlAgentEnrollmentRepository(session2)
        x1 = await repo1.get_by_id(x.enrollment.id, org.org_id)
        x2 = await repo2.get_by_id(x.enrollment.id, org.org_id)
        assert x1 is not None and x2 is not None

        results = await asyncio.gather(
            agent_token.rotate(repo1, x1, created_by_user_id=org.owner.user_id, now=now),
            agent_token.rotate(repo2, x2, created_by_user_id=org.owner.user_id, now=now),
            return_exceptions=True,
        )

    issued = [r for r in results if isinstance(r, IssuedToken)]
    refused = [r for r in results if isinstance(r, AgentNotActiveError)]
    assert len(issued) == 1, results
    assert len(refused) == 1, results
    assert await _successor_ids(x.enrollment.id) == [issued[0].enrollment.id]


async def test_revoke_mid_chain_waits_for_inflight_claim(world, authz_client, as_user, clock):
    """A revoke through a mid-chain row waits for an in-flight claim on the chain, then covers the successor."""
    org = world.a
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(org)
    x_id = x.enrollment.id
    admin = await as_user(org.admin)
    s1_id, _ = await _rotate_ok(admin, x_id)
    s2_id, _ = await _rotate_ok(admin, s1_id)
    now = t0 + GRACE + timedelta(hours=1)
    clock(now)

    session1 = AsyncSessionLocal()
    session2 = AsyncSessionLocal()
    task = None
    try:
        repo1 = SqlAgentEnrollmentRepository(session1)
        p1 = (await session1.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        s2 = await repo1.get_by_id(s2_id, org.org_id)
        assert s2 is not None
        name, scopes = s2.name, s2.scopes
        # The real claim: takes the root lock and the row; left uncommitted.
        assert await repo1.claim_for_rotation(s2, grace_until=now + GRACE, now=now)

        await session2.execute(text("SET LOCAL lock_timeout = '10s'"))
        p2 = (await session2.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        repo2 = SqlAgentEnrollmentRepository(session2)
        s1 = await repo2.get_by_id(s1_id, org.org_id)
        assert s1 is not None
        task = asyncio.create_task(agent_token.revoke(repo2, s1))

        await wait_until_blocked(p2, blocker=p1)

        s3 = await agent_token.issue(
            repo1,
            org_id=org.org_id,
            name=name,
            scopes=scopes,
            created_by_user_id=org.owner.user_id,
            now=now,
            chain_root_id=x_id,
        )
        ids = await asyncio.wait_for(task, 10)

        assert s3.enrollment.id in ids
        assert s2_id in ids
        await assert_refused(await authz_client(s3.raw_token), STATUS, world)
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
