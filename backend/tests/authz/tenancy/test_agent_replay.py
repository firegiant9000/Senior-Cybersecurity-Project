"""Replay of an agent scan upload is refused, with the fast path and with the DB backstop.

Real clock and real verifier; no `clock` fixture. The one patch (backstop test) removes the fast
path so the unique constraint has to answer.
"""

from sqlalchemy import func, select

from app.db.agent_scan_nonce import AgentScanNonce
from app.db.engine import AsyncSessionLocal
from app.db.scan_run import ScanRun
from app.repositories.agent_scan_nonces import SqlAgentScanNonceRepository
from tests.authz.tenancy._agents import REPLAY_DETAIL, issue_agent, scan_payload
from tests.authz.tenancy._world import snapshot_org

UPLOAD_URL = "/api/v1/inventory/scans"


async def _upload(client, payload):
    return await client.post(UPLOAD_URL, json=payload)


async def test_replayed_upload_rejected(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    p = scan_payload(world.a)
    first = await _upload(client, p)
    assert first.status_code == 201, first.text
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _upload(client, p)

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == REPLAY_DETAIL
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_replay_rejected_after_rotation(world, authz_client, as_user):
    issued = await issue_agent(world.a)
    client = await authz_client(issued.raw_token)
    p = scan_payload(world.a)
    first = await _upload(client, p)
    assert first.status_code == 201, first.text
    admin = await as_user(world.a.admin)
    rotated = await admin.post(f"/api/v1/agents/{issued.enrollment.id}/rotate")
    assert rotated.status_code == 200, rotated.text
    successor = await authz_client(rotated.json()["raw_token"])
    # The successor's first verify sets last_used_at; warm it so the debounce covers the replay.
    warm = await successor.get(f"/api/v1/inventory/scans/{world.a.ids['scan_run_id']}")
    assert warm.status_code == 200, warm.text
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await _upload(successor, p)

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == REPLAY_DETAIL
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_replay_backstop_unique_constraint(world, authz_client, monkeypatch):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    p = scan_payload(world.a)
    first = await _upload(client, p)
    assert first.status_code == 201, first.text
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    async def _never_seen(*_args, **_kwargs):
        return False

    monkeypatch.setattr(SqlAgentScanNonceRepository, "seen_within", _never_seen)
    resp = await _upload(client, p)

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == REPLAY_DETAIL
    after = await snapshot_org(world.a.org_id, world.upload_dir)
    changed = {t for t in after if after[t] != before[t]}
    assert changed == {"scan_runs"}
    assert len(after["scan_runs"]) == len(before["scan_runs"]) + 1
    async with AsyncSessionLocal() as session:
        nonces = (
            await session.execute(
                select(func.count())
                .select_from(AgentScanNonce)
                .where(AgentScanNonce.scan_id == p["scan_id"], AgentScanNonce.nonce == p["nonce"])
            )
        ).scalar_one()
        failed = (
            (
                await session.execute(
                    select(ScanRun)
                    .where(ScanRun.org_id == world.a.org_id, ScanRun.status == "failed")
                    .order_by(ScanRun.id.desc())
                )
            )
            .scalars()
            .first()
        )
    assert nonces == 1
    assert failed is not None
    assert failed.error_message == "duplicate scan submission"
