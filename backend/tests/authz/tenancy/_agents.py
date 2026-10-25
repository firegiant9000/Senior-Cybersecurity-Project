"""Helpers for the agent-token lifecycle tests: issue real agents, build agent requests.

Agents are issued through the real service against the real DB, so the real verifier decides.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from app.services.agent_token import IssuedToken
from tests.authz.tenancy._cases import Req
from tests.authz.tenancy._world import OrgWorld, snapshot_org

AGENT_DENIED = "Invalid or expired agent token"
REPLAY_DETAIL = "Duplicate scan submission (replay detected)"
NOT_ACTIVE = "Only an active agent can be rotated"  # used from Task 3
NOT_IN_GRACE = "Only an agent in its grace window can be ended"
GRACE = timedelta(hours=settings.AGENT_TOKEN_ROTATION_GRACE_HOURS)

UPLOAD = ("POST", "/api/v1/inventory/scans")
STATUS = ("GET", "/api/v1/inventory/scans/{scan_run_id}")
AGENT_ROUTES: tuple[tuple[str, str], ...] = (UPLOAD, STATUS)
ACCEPTED: dict[tuple[str, str], int] = {UPLOAD: 201, STATUS: 200}

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "agent_scan_v1.json"


def frozen_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def scan_payload(org: OrgWorld) -> dict:
    """The golden scan with a fresh scan_id and nonce (the nonce table is globally unique)."""
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    payload["scan_id"] = str(uuid.uuid4())
    payload["nonce"] = uuid.uuid4().hex
    payload["host"]["hostname"] = f"{org.marker}-agent-host"
    return payload


def agent_request(route: tuple[str, str], org: OrgWorld) -> Req:
    if route == UPLOAD:
        return Req("POST", UPLOAD[1], json=scan_payload(org))
    return Req("GET", STATUS[1].format(scan_run_id=org.ids["scan_run_id"]))


async def issue_agent(
    org: OrgWorld,
    *,
    now: datetime | None = None,
    expires_at: datetime | None = None,
    name: str | None = None,
) -> IssuedToken:
    assert org.owner is not None
    async with AsyncSessionLocal() as session:
        issued = await agent_token.issue(
            SqlAgentEnrollmentRepository(session),
            org_id=org.org_id,
            name=name or f"{org.marker}-agent-{uuid.uuid4().hex[:6]}",
            scopes=["scan:upload"],
            created_by_user_id=org.owner.user_id,
            expires_at=expires_at,
            now=now,
        )
        await session.commit()
        return issued


async def load_agent(agent_id: int) -> AgentEnrollment:
    async with AsyncSessionLocal() as session:
        row = await session.get(AgentEnrollment, agent_id)
        assert row is not None
        return row


async def wait_until_blocked(pid: int, *, blocker: int, timeout: float = 5.0) -> None:
    """Poll until backend `pid` is waiting on a lock held by backend `blocker`.

    Each poll uses a fresh session (its own transaction) because `pg_stat_activity` is
    snapshotted per transaction. Scoped to the two pids so another backend can't satisfy it.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT 1 FROM pg_stat_activity WHERE pid = :pid "
                        "AND wait_event_type = 'Lock' "
                        "AND :blocker = ANY(pg_blocking_pids(:pid))"
                    ),
                    {"pid": pid, "blocker": blocker},
                )
            ).first()
        if row is not None:
            return
        if loop.time() >= deadline:
            raise AssertionError("revoke did not wait for the chain lock")
        await asyncio.sleep(0.05)


async def send(client, req: Req) -> httpx.Response:
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )


async def assert_refused(client, route, world):
    """The agent call is exactly 401 with the Bearer challenge, and changes nothing in the org."""
    req = agent_request(route, world.a)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await send(client, req)

    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == AGENT_DENIED
    assert resp.headers["www-authenticate"] == "Bearer"
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def assert_accepted(client, route, world):
    resp = await send(client, agent_request(route, world.a))
    assert resp.status_code == ACCEPTED[route], resp.text
