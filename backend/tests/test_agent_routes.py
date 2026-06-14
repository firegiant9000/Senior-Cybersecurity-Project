"""Route tests for the Month 4 Phase 2 agent enrollment API.

Covers enroll (token shown once) / list / rotate / revoke, plus the two access
boundaries the plan calls out: non-admins get 403, and a cross-org agent id 404s.
The token service is exercised directly in ``test_agent_token.py``; here we mock
the repo and assert the route wiring, auth gate, and audit-safe commit path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import get_current_org, require_org_role
from app.db.engine import get_session
from app.main import app
from app.repositories.agent_enrollments import get_agent_enrollment_repo
from app.services import agent_token


def _enrollment(**overrides):
    base = {
        "id": 1,
        "org_id": 1,
        "name": "web-01",
        "token_prefix": "deadbeef",
        "scopes": None,
        "created_by_user_id": 7,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_used_at": None,
        "revoked_at": None,
        "expires_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeSession:
    """Minimal session stand-in: agent routes only call add/flush/commit for audit."""

    def add(self, _obj):  # noqa: ANN001
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


async def _admin_user():
    return SimpleNamespace(id=7, email="admin@example.com", org_id=1, org_role="admin")


async def _org():
    return SimpleNamespace(id=1, name="Acme")


def _override_admin(repo):
    app.dependency_overrides[require_org_role("admin")] = _admin_user
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_current_org] = _org
    app.dependency_overrides[get_agent_enrollment_repo] = lambda: repo
    app.dependency_overrides[get_session] = lambda: _FakeSession()


def _clear_overrides():
    for dep in (
        require_org_role("admin"),
        get_current_user,
        get_current_org,
        get_agent_enrollment_repo,
        get_session,
    ):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.asyncio
async def test_enroll_returns_raw_token_once(client: AsyncClient, monkeypatch):
    repo = MagicMock()
    issued = SimpleNamespace(enrollment=_enrollment(), raw_token="ht_deadbeef_supersecret")
    monkeypatch.setattr(agent_token, "issue", AsyncMock(return_value=issued))

    _override_admin(repo)
    try:
        resp = await client.post("/api/v1/agents/enroll", json={"name": "web-01"})
    finally:
        _clear_overrides()

    assert resp.status_code == 201
    data = resp.json()
    assert data["raw_token"] == "ht_deadbeef_supersecret"
    assert data["agent"]["token_prefix"] == "deadbeef"
    # The safe view never leaks the hash.
    assert "token_hash" not in data["agent"]


@pytest.mark.asyncio
async def test_list_agents_returns_org_rows(client: AsyncClient):
    repo = MagicMock()
    repo.list_for_org = AsyncMock(return_value=[_enrollment(), _enrollment(id=2, name="db-01")])

    _override_admin(repo)
    try:
        resp = await client.get("/api/v1/agents")
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert {a["name"] for a in data["items"]} == {"web-01", "db-01"}


@pytest.mark.asyncio
async def test_rotate_issues_new_token(client: AsyncClient, monkeypatch):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_enrollment())
    rotated = SimpleNamespace(enrollment=_enrollment(id=2), raw_token="ht_newpfx_newsecret")
    monkeypatch.setattr(agent_token, "rotate", AsyncMock(return_value=rotated))

    _override_admin(repo)
    try:
        resp = await client.post("/api/v1/agents/1/rotate")
    finally:
        _clear_overrides()

    assert resp.status_code == 200
    assert resp.json()["raw_token"] == "ht_newpfx_newsecret"


@pytest.mark.asyncio
async def test_revoke_returns_204(client: AsyncClient, monkeypatch):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_enrollment())
    revoke_mock = AsyncMock(return_value=_enrollment(revoked_at=datetime.now(UTC)))
    monkeypatch.setattr(agent_token, "revoke", revoke_mock)

    _override_admin(repo)
    try:
        resp = await client.delete("/api/v1/agents/1")
    finally:
        _clear_overrides()

    assert resp.status_code == 204
    revoke_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_rotate_unknown_or_cross_org_id_404(client: AsyncClient):
    repo = MagicMock()
    # get_by_id is org-scoped, so a cross-org id resolves to None.
    repo.get_by_id = AsyncMock(return_value=None)

    _override_admin(repo)
    try:
        resp = await client.post("/api/v1/agents/999/rotate")
    finally:
        _clear_overrides()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_unknown_or_cross_org_id_404(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)

    _override_admin(repo)
    try:
        resp = await client.delete("/api/v1/agents/999")
    finally:
        _clear_overrides()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_enroll_non_admin_forbidden(client: AsyncClient):
    async def _deny():
        raise HTTPException(status_code=403, detail="Insufficient organization role")

    app.dependency_overrides[require_org_role("admin")] = _deny
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = await client.post("/api/v1/agents/enroll", json={"name": "web-01"})
    finally:
        app.dependency_overrides.pop(require_org_role("admin"), None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
