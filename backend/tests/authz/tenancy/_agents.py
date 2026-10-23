"""Helpers for the agent-token lifecycle tests: issue real agents, build agent requests.

Agents are issued through the real service against the real DB, so the real verifier decides.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.core.config import settings
from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import AsyncSessionLocal
from app.repositories.agent_enrollments import SqlAgentEnrollmentRepository
from app.services import agent_token
from app.services.agent_token import IssuedToken
from tests.authz.tenancy._cases import Req
from tests.authz.tenancy._world import OrgWorld

AGENT_DENIED = "Invalid or expired agent token"
REPLAY_DETAIL = "Duplicate scan submission (replay detected)"
NOT_ACTIVE = "Only an active agent can be rotated"  # used from Task 3
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


async def send(client, req: Req) -> httpx.Response:
    return await client.request(
        req.method, req.url, params=req.params, json=req.json, files=req.files
    )
