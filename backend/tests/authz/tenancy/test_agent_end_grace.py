"""Ending a predecessor's grace window affects only that row (T-TOK-08).

Rotate and end-grace go through the real management routes; the agent checks use the real
verifier. The concurrency tests drive the service and repository with separate sessions against
the real DB. The only patch is the service clock (`clock` fixture).
"""

import asyncio
from datetime import timedelta

from sqlalchemy import select, text

from app.db.audit_log import AuditLog
from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from app.services.agent_token import AgentNotInGraceError
from tests.authz.tenancy._agents import (
    GRACE,
    NOT_IN_GRACE,
    STATUS,
    UPLOAD,
    assert_accepted,
    assert_refused,
    frozen_now,
    issue_agent,
    load_agent,
    wait_until_blocked,
)
from tests.authz.tenancy._roles import ROLE_DENIED
from tests.authz.tenancy._world import snapshot_org


async def _rotate(admin, agent_id: int) -> tuple[int, str]:
    resp = await admin.post(f"/api/v1/agents/{agent_id}/rotate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["agent"]["id"], body["raw_token"]


async def _end_grace(client, agent_id: int):
    return await client.post(f"/api/v1/agents/{agent_id}/end-grace")


async def _assert_refused_409(admin, agent_id: int, world) -> None:
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _end_grace(admin, agent_id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == NOT_IN_GRACE
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_end_grace_kills_predecessor_keeps_successor(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s_id, s_token = await _rotate(admin, x.enrollment.id)
    # Inside grace, the predecessor still works.
    await assert_accepted(await authz_client(x.raw_token), STATUS, world)
    later = t0 + timedelta(hours=1)
    clock(later)

    resp = await _end_grace(admin, x.enrollment.id)

    assert resp.status_code == 204, resp.text
    await assert_refused(await authz_client(x.raw_token), UPLOAD, world)
    await assert_refused(await authz_client(x.raw_token), STATUS, world)
    await assert_accepted(await authz_client(s_token), UPLOAD, world)
    assert (await load_agent(x.enrollment.id)).revoked_at == later
    assert (await load_agent(s_id)).revoked_at is None


async def test_end_grace_is_audited(world, as_user, clock):
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)

    resp = await _end_grace(admin, x.enrollment.id)

    assert resp.status_code == 204, resp.text
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.org_id == world.a.org_id, AuditLog.action == "agent.end_grace")
                .order_by(AuditLog.id.desc())
                .limit(1)
            )
        ).scalar_one()
    assert row.payload == {"agent_id": x.enrollment.id}


async def test_end_grace_refused_when_active(world, authz_client, as_user, clock):
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at is None
    await assert_accepted(await authz_client(x.raw_token), STATUS, world)


async def test_end_grace_refused_when_revoked(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    assert (await admin.delete(f"/api/v1/agents/{x.enrollment.id}")).status_code == 204
    clock(t0 + timedelta(hours=1))

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0


async def test_end_grace_refused_when_expired(world, as_user, clock):
    t0 = frozen_now()
    x = await issue_agent(world.a, now=t0 - timedelta(days=1), expires_at=t0)
    clock(t0)
    admin = await as_user(world.a.admin)

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at is None


async def test_end_grace_refused_after_grace_elapsed(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)
    clock(t0 + GRACE + timedelta(hours=1))

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_end_grace_refused_when_expired_but_still_in_grace_window(world, as_user, clock):
    """Rotated, then expired before the grace ended: `revoked_at` is in the future but the row is dead."""
    t0 = frozen_now()
    x = await issue_agent(world.a, now=t0, expires_at=t0 + timedelta(hours=2))
    clock(t0)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)
    clock(t0 + timedelta(hours=3))

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_repository_end_grace_refuses_expired_row(world):
    org = world.a
    t0 = frozen_now()
    x = await issue_agent(org, now=t0, expires_at=t0 + timedelta(hours=2))
    session = AsyncSessionLocal()
    try:
        repo = SqlAgentEnrollmentRepository(session)
        row = await repo.get_by_id(x.enrollment.id, org.org_id)
        assert row is not None
        assert await repo.claim_for_rotation(row, grace_until=t0 + GRACE, now=t0)
        await session.commit()

        ended = await repo.end_grace(row, when=t0 + timedelta(hours=3))

        assert ended is False
    finally:
        try:
            await session.rollback()
        finally:
            await session.close()
    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_end_grace_twice_never_moves_revoked_at_later(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)
    first = t0 + timedelta(hours=1)
    clock(first)
    assert (await _end_grace(admin, x.enrollment.id)).status_code == 204
    clock(first + timedelta(hours=1))

    await _assert_refused_409(admin, x.enrollment.id, world)

    assert (await load_agent(x.enrollment.id)).revoked_at == first


async def test_repository_end_grace_never_moves_later(world):
    """With a `when` after the row's `revoked_at`, the database's own condition refuses."""
    org = world.a
    t0 = frozen_now()
    x = await issue_agent(org, now=t0)
    session = AsyncSessionLocal()
    try:
        repo = SqlAgentEnrollmentRepository(session)
        row = await repo.get_by_id(x.enrollment.id, org.org_id)
        assert row is not None
        assert await repo.claim_for_rotation(row, grace_until=t0 + GRACE, now=t0)
        await session.commit()

        ended = await repo.end_grace(row, when=t0 + GRACE + timedelta(hours=1))

        assert ended is False
    finally:
        try:
            await session.rollback()
        finally:
            await session.close()
    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_chain_revoke_after_end_grace_still_covers_chain(world, authz_client, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    s_id, s_token = await _rotate(admin, x.enrollment.id)
    ended = t0 + timedelta(hours=1)
    clock(ended)
    assert (await _end_grace(admin, x.enrollment.id)).status_code == 204
    clock(ended + timedelta(hours=1))

    resp = await admin.delete(f"/api/v1/agents/{x.enrollment.id}")

    assert resp.status_code == 204, resp.text
    await assert_refused(await authz_client(s_token), STATUS, world)
    assert (await load_agent(x.enrollment.id)).revoked_at == ended
    assert (await load_agent(s_id)).revoked_at == ended + timedelta(hours=1)


async def test_chain_revoke_in_grace_still_revokes_successor(world, authz_client, as_user, clock):
    """Chain-wide revoke is unchanged: revoking the predecessor in grace also kills the successor."""
    clock(frozen_now())
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    _, s_token = await _rotate(admin, x.enrollment.id)

    resp = await admin.delete(f"/api/v1/agents/{x.enrollment.id}")

    assert resp.status_code == 204, resp.text
    await assert_refused(await authz_client(s_token), STATUS, world)


async def test_member_cannot_end_grace(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)
    member = await as_user(world.a.member)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _end_grace(member, x.enrollment.id)

    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == ROLE_DENIED
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_other_org_admin_gets_404(world, as_user, clock):
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(world.a)
    admin = await as_user(world.a.admin)
    await _rotate(admin, x.enrollment.id)
    other = await as_user(world.b.admin)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _end_grace(other, x.enrollment.id)

    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Agent not found"
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    assert (await load_agent(x.enrollment.id)).revoked_at == t0 + GRACE


async def test_concurrent_end_grace_one_wins(world):
    org = world.a
    t0 = frozen_now()
    x = await issue_agent(org, now=t0)
    now = t0 + timedelta(hours=1)
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        repo1 = SqlAgentEnrollmentRepository(session1)
        repo2 = SqlAgentEnrollmentRepository(session2)
        row = await repo1.get_by_id(x.enrollment.id, org.org_id)
        assert row is not None
        await agent_token.rotate(repo1, row, created_by_user_id=org.owner.user_id, now=t0)
        x1 = await repo1.get_by_id(x.enrollment.id, org.org_id)
        x2 = await repo2.get_by_id(x.enrollment.id, org.org_id)
        assert x1 is not None and x2 is not None

        results = await asyncio.gather(
            agent_token.end_grace(repo1, x1, now=now),
            agent_token.end_grace(repo2, x2, now=now),
            return_exceptions=True,
        )

    assert sum(r is None for r in results) == 1, results
    assert sum(isinstance(r, AgentNotInGraceError) for r in results) == 1, results
    assert (await load_agent(x.enrollment.id)).revoked_at == now


async def test_end_grace_waits_for_chain_lock_then_leaves_successor(
    world, authz_client, as_user, clock
):
    """End-grace on a mid-chain row waits for the lock on the chain ROOT, then applies to that row only.

    X -> S1 -> S2: S1 is in grace. The lock is held on X only, so only the chain-root lock
    (not S1's own row lock) can make the end-grace on S1 wait.
    """
    org = world.a
    t0 = frozen_now()
    clock(t0)
    x = await issue_agent(org)
    x_id = x.enrollment.id
    admin = await as_user(org.admin)
    s1_id, _ = await _rotate(admin, x_id)
    s2_id, s_token = await _rotate(admin, s1_id)
    now = t0 + timedelta(hours=1)
    clock(now)

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
        s1 = await repo2.get_by_id(s1_id, org.org_id)
        assert s1 is not None
        task = asyncio.create_task(agent_token.end_grace(repo2, s1, now=now))

        await wait_until_blocked(p2, blocker=p1)
        assert not task.done()
        await session1.commit()
        await asyncio.wait_for(task, 10)

        assert (await load_agent(s1_id)).revoked_at == now
        assert (await load_agent(x_id)).revoked_at == t0 + GRACE
        assert (await load_agent(s2_id)).revoked_at is None
        await assert_accepted(await authz_client(s_token), STATUS, world)
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


async def test_end_grace_and_chain_revoke_concurrent(world):
    """Whichever order they run, X ends at the earlier time and the successor at the later one."""
    org = world.a
    t0 = frozen_now()
    x = await issue_agent(org, now=t0)
    now = t0 + timedelta(hours=1)
    later = t0 + timedelta(hours=2)
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        repo1 = SqlAgentEnrollmentRepository(session1)
        repo2 = SqlAgentEnrollmentRepository(session2)
        row = await repo1.get_by_id(x.enrollment.id, org.org_id)
        assert row is not None
        succ = await agent_token.rotate(repo1, row, created_by_user_id=org.owner.user_id, now=t0)
        x1 = await repo1.get_by_id(x.enrollment.id, org.org_id)
        x2 = await repo2.get_by_id(x.enrollment.id, org.org_id)
        assert x1 is not None and x2 is not None

        end_result, revoke_result = await asyncio.gather(
            agent_token.end_grace(repo1, x1, now=now),
            agent_token.revoke(repo2, x2, now=later),
            return_exceptions=True,
        )

    assert end_result is None or isinstance(end_result, AgentNotInGraceError), end_result
    assert isinstance(revoke_result, list), revoke_result
    # Earlier of the two times, in either order; never moved later.
    assert (await load_agent(x.enrollment.id)).revoked_at == now
    # The chain revoke always runs, so the successor is revoked in either order.
    assert (await load_agent(succ.enrollment.id)).revoked_at == later
