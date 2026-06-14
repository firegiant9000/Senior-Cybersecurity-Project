"""Route tests for the Month 4 Phase 3 agent scan-upload endpoint.

Covers the happy path (persist scan_run → commit_inventory → matcher kicked),
the version gates (422 unknown schema, 426 below-min scanner), replay rejection
(409 both fast-path and the unique-constraint race), agent-token auth (401), and
the org-scoped status poll. The pure ingest helpers are unit-tested in
``test_agent_scan_service.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

import app.api.routes.v1.inventory as inventory_module
from app.core.dependencies import get_agent_from_token
from app.db.engine import get_session
from app.main import app
from app.repositories.agent_scan_nonces import get_agent_scan_nonce_repo
from app.repositories.assets import get_asset_repo
from app.repositories.scan_runs import get_scan_run_repo

GOLDEN = Path(__file__).parent / "fixtures" / "agent_scan_v1.json"


def _payload(**overrides) -> dict:
    data = json.loads(GOLDEN.read_text())
    data.update(overrides)
    return data


class _FakeSession:
    def add(self, _obj):  # noqa: ANN001
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _enrollment():
    return SimpleNamespace(id=1, org_id=1, scopes=None)


def _scan_run(status="pending", **overrides):
    base = {
        "id": 99,
        "org_id": 1,
        "source": "agent",
        "status": status,
        "started_at": datetime(2026, 1, 1, tzinfo=UTC),
        "finished_at": None,
        "asset_count": 0,
        "software_count": 0,
        "error_message": None,
        "scan_metadata": None,
        "triggered_by_user_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _override(*, enrollment=None, scan_repo=None, nonce_repo=None, asset_repo=None):
    app.dependency_overrides[get_agent_from_token] = lambda: enrollment or _enrollment()
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    app.dependency_overrides[get_scan_run_repo] = lambda: scan_repo
    app.dependency_overrides[get_agent_scan_nonce_repo] = lambda: nonce_repo
    # Default: no matching asset, so the services/ports persistence is a no-op
    # unless a test supplies an asset_repo that resolves one.
    repo = asset_repo or _asset_repo()
    app.dependency_overrides[get_asset_repo] = lambda: repo


def _asset_repo(asset=None):
    repo = MagicMock()
    repo.get_by_hostname = AsyncMock(return_value=asset)
    return repo


def _clear():
    for dep in (
        get_agent_from_token,
        get_session,
        get_scan_run_repo,
        get_agent_scan_nonce_repo,
        get_asset_repo,
    ):
        app.dependency_overrides.pop(dep, None)


def _scan_repo_success():
    repo = MagicMock()
    repo.create = AsyncMock(return_value=_scan_run(id=99, status="pending"))
    repo.update = AsyncMock(
        return_value=_scan_run(id=99, status="succeeded", asset_count=1, software_count=3)
    )
    return repo


def _nonce_repo(*, seen=False):
    repo = MagicMock()
    repo.seen_within = AsyncMock(return_value=seen)
    repo.record = AsyncMock(return_value=SimpleNamespace(id=1))
    return repo


@pytest.mark.asyncio
async def test_upload_happy_path_persists_and_triggers_matcher(client: AsyncClient, monkeypatch):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo(seen=False)
    monkeypatch.setattr(inventory_module, "commit_inventory", AsyncMock(return_value=(1, 3)))
    triggered = MagicMock()
    monkeypatch.setattr("app.workers.matcher_job.trigger_matcher_async", triggered)

    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload())
    finally:
        _clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["scan_run_id"] == 99
    assert data["status"] == "succeeded"
    assert data["asset_count"] == 1
    assert data["software_count"] == 3
    nonce_repo.record.assert_awaited_once()
    triggered.assert_called_once()
    assert triggered.call_args.kwargs.get("trigger") == "agent_scan"


@pytest.mark.asyncio
async def test_upload_persists_services_and_ports_on_asset(client: AsyncClient, monkeypatch):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo(seen=False)
    monkeypatch.setattr(inventory_module, "commit_inventory", AsyncMock(return_value=(1, 3)))
    monkeypatch.setattr("app.workers.matcher_job.trigger_matcher_async", MagicMock())

    asset = SimpleNamespace(services=None, listening_ports=None)
    _override(scan_repo=scan_repo, nonce_repo=nonce_repo, asset_repo=_asset_repo(asset))
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload())
    finally:
        _clear()

    assert resp.status_code == 201
    # The golden payload carries 2 services and 2 ports; both land on the asset.
    assert asset.services == [
        {"name": "nginx.service", "state": "running"},
        {"name": "ssh.service", "state": "running"},
    ]
    assert asset.listening_ports == [
        {"port": 443, "protocol": "tcp", "process": "nginx"},
        {"port": 22, "protocol": "tcp", "process": "sshd"},
    ]


@pytest.mark.asyncio
async def test_upload_without_services_or_ports_leaves_asset_untouched(
    client: AsyncClient, monkeypatch
):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo(seen=False)
    monkeypatch.setattr(inventory_module, "commit_inventory", AsyncMock(return_value=(1, 3)))
    monkeypatch.setattr("app.workers.matcher_job.trigger_matcher_async", MagicMock())

    # Prior scan data on the asset must not be clobbered when this scan reports
    # neither services nor ports (empty lists → None → skip the write).
    asset = SimpleNamespace(services=[{"name": "old"}], listening_ports=[{"port": 1}])
    _override(scan_repo=scan_repo, nonce_repo=nonce_repo, asset_repo=_asset_repo(asset))
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload(services=[], ports=[]))
    finally:
        _clear()

    assert resp.status_code == 201
    assert asset.services == [{"name": "old"}]
    assert asset.listening_ports == [{"port": 1}]


@pytest.mark.asyncio
async def test_upload_unsupported_schema_version_422(client: AsyncClient):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo()
    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload(schema_version="99.0"))
    finally:
        _clear()
    assert resp.status_code == 422
    scan_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_below_min_scanner_version_426(client: AsyncClient):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo()
    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload(scanner_version="0.0.1"))
    finally:
        _clear()
    assert resp.status_code == 426
    scan_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_replay_fast_path_409(client: AsyncClient):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo(seen=True)  # already seen within window
    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload())
    finally:
        _clear()
    assert resp.status_code == 409
    # Rejected before creating an orphan scan_run.
    scan_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_concurrent_replay_unique_violation_409(client: AsyncClient, monkeypatch):
    scan_repo = _scan_repo_success()
    nonce_repo = _nonce_repo(seen=False)
    nonce_repo.record = AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("unique violation"))
    )
    monkeypatch.setattr(inventory_module, "commit_inventory", AsyncMock(return_value=(1, 3)))

    _override(scan_repo=scan_repo, nonce_repo=nonce_repo)
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload())
    finally:
        _clear()

    assert resp.status_code == 409
    # The orphan scan_run was created then marked failed.
    scan_repo.create.assert_awaited_once()
    failed = [c for c in scan_repo.update.await_args_list if c.args[2].status == "failed"]
    assert failed


@pytest.mark.asyncio
async def test_upload_requires_agent_token_401(client: AsyncClient):
    async def _deny():
        raise HTTPException(status_code=401, detail="Invalid or expired agent token")

    app.dependency_overrides[get_agent_from_token] = _deny
    try:
        resp = await client.post("/api/v1/inventory/scans", json=_payload())
    finally:
        app.dependency_overrides.pop(get_agent_from_token, None)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_scan_status_org_scoped(client: AsyncClient):
    scan_repo = MagicMock()
    scan_repo.get_by_id = AsyncMock(return_value=_scan_run(id=99, status="succeeded"))
    _override(scan_repo=scan_repo, nonce_repo=_nonce_repo())
    try:
        resp = await client.get("/api/v1/inventory/scans/99")
    finally:
        _clear()
    assert resp.status_code == 200
    assert resp.json()["id"] == 99
    # Lookup is scoped to the token's org (enrollment.org_id == 1).
    scan_repo.get_by_id.assert_awaited_once_with(99, 1)


@pytest.mark.asyncio
async def test_get_scan_status_unknown_404(client: AsyncClient):
    scan_repo = MagicMock()
    scan_repo.get_by_id = AsyncMock(return_value=None)
    _override(scan_repo=scan_repo, nonce_repo=_nonce_repo())
    try:
        resp = await client.get("/api/v1/inventory/scans/12345")
    finally:
        _clear()
    assert resp.status_code == 404
