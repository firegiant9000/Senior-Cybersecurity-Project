"""Tests for the Phase B3 skip / complete intake endpoints.

These endpoints persist user intent (which steps were dismissed, and
whether the wizard was completed) on the organizations row so the
wizard wall doesn't re-pop on the user's next login (R9 mitigation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import get_current_org
from app.db.engine import get_session
from app.db.organization import Organization
from app.db.user import User
from app.main import app


def _make_org(**overrides) -> Organization:
    org = MagicMock(spec=Organization)
    org.id = overrides.get("id", 42)
    org.intake_skipped_steps = overrides.get("intake_skipped_steps", None)
    org.intake_completed_at = overrides.get("intake_completed_at", None)
    return org


def _user_override():
    async def _override():
        u = MagicMock(spec=User)
        u.id = 1
        u.org_id = 42
        return u

    return _override


def _session_override():
    async def _override():
        sess = MagicMock()
        sess.commit = AsyncMock()
        sess.refresh = AsyncMock()
        sess.rollback = AsyncMock()
        return sess

    return _override


@pytest.mark.asyncio
async def test_skip_records_step_on_org(client: AsyncClient):
    org = _make_org(intake_skipped_steps=None)

    async def _org_override():
        return org

    app.dependency_overrides[get_current_user] = _user_override()
    app.dependency_overrides[get_current_org] = _org_override
    app.dependency_overrides[get_session] = _session_override()
    try:
        resp = await client.post(
            "/api/v1/organizations/mine/intake/skip",
            json={"step": "financial_compliance"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "financial_compliance" in body["skipped_steps"]
    # Persisted on the ORM object so a subsequent read picks it up.
    assert "financial_compliance" in (org.intake_skipped_steps or [])


@pytest.mark.asyncio
async def test_skip_is_idempotent(client: AsyncClient):
    org = _make_org(intake_skipped_steps=["financial_compliance"])

    async def _org_override():
        return org

    app.dependency_overrides[get_current_user] = _user_override()
    app.dependency_overrides[get_current_org] = _org_override
    app.dependency_overrides[get_session] = _session_override()
    try:
        resp = await client.post(
            "/api/v1/organizations/mine/intake/skip",
            json={"step": "financial_compliance"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # No duplicate entry.
    assert body["skipped_steps"].count("financial_compliance") == 1


@pytest.mark.asyncio
async def test_complete_sets_timestamp(client: AsyncClient):
    org = _make_org()

    async def _org_override():
        return org

    app.dependency_overrides[get_current_user] = _user_override()
    app.dependency_overrides[get_current_org] = _org_override
    app.dependency_overrides[get_session] = _session_override()
    try:
        resp = await client.post("/api/v1/organizations/mine/intake/complete")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completed_at"] is not None
    assert org.intake_completed_at is not None


@pytest.mark.asyncio
async def test_skip_requires_auth(anon_client: AsyncClient):
    resp = await anon_client.post(
        "/api/v1/organizations/mine/intake/skip",
        json={"step": "financial_compliance"},
    )
    assert resp.status_code in (401, 403)
