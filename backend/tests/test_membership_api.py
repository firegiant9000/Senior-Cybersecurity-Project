"""Tests for org membership invite acceptance and same-org access boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.api.routes.v1.auth import get_current_user
from app.core.dependencies import require_same_org_membership
from app.db.engine import get_session
from app.main import app
from app.repositories.org_invite import get_invite_repo


class _BeginCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


class _FakeSession:
    def begin(self):
        return _BeginCtx()

    def add(self, _obj):  # noqa: ANN001
        return None

    async def commit(self):
        return None


async def _user_for_email(email: str, user_id: int = 101):
    return SimpleNamespace(id=user_id, email=email, org_id=None, org_role=None)


async def _fake_member_user():
    return await _user_for_email("member@example.com")


async def _fake_outsider_user():
    return await _user_for_email("outsider@example.com")


@pytest.mark.asyncio
async def test_accept_invite_with_fake_user_success(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_token_for_update = AsyncMock(
        return_value=SimpleNamespace(
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email="member@example.com",
            org_id=1,
            role="member",
        )
    )
    repo.get_active_membership = AsyncMock(return_value=None)
    repo.create_membership = AsyncMock()
    repo.mark_accepted = AsyncMock()

    app.dependency_overrides[get_invite_repo] = lambda: repo
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        resp = await client.post("/api/v1/invites/fake-token/accept")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["detail"] == "Invite accepted"
    repo.create_membership.assert_awaited_once()
    repo.mark_accepted.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_invite_with_different_user_email_forbidden(client: AsyncClient):
    repo = MagicMock()
    repo.get_by_token_for_update = AsyncMock(
        return_value=SimpleNamespace(
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email="invited@example.com",
            org_id=1,
            role="member",
        )
    )
    repo.get_active_membership = AsyncMock(return_value=None)
    repo.create_membership = AsyncMock()
    repo.mark_accepted = AsyncMock()

    app.dependency_overrides[get_invite_repo] = lambda: repo
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    app.dependency_overrides[get_current_user] = _fake_outsider_user
    try:
        resp = await client.post("/api/v1/invites/fake-token/accept")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    repo.create_membership.assert_not_awaited()
    repo.mark_accepted.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_members_same_org_allowed(client: AsyncClient):
    repo = MagicMock()
    repo.list_members_with_users = AsyncMock(
        return_value=(
            [
                (
                    SimpleNamespace(user_id=1, role="member", status="active"),
                    SimpleNamespace(email="member@example.com", is_active=True),
                )
            ],
            1,
        )
    )

    async def _allow_same_org():
        return SimpleNamespace(role="member", org_id=1, status="active")

    app.dependency_overrides[get_invite_repo] = lambda: repo
    app.dependency_overrides[require_same_org_membership] = _allow_same_org
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        resp = await client.get("/api/v1/orgs/1/members")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(require_same_org_membership, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "member@example.com"


@pytest.mark.asyncio
async def test_list_members_different_org_forbidden(client: AsyncClient):
    async def _deny_same_org():
        raise HTTPException(status_code=403, detail="Access denied for this organization")

    app.dependency_overrides[require_same_org_membership] = _deny_same_org
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        resp = await client.get("/api/v1/orgs/1/members")
    finally:
        app.dependency_overrides.pop(require_same_org_membership, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
