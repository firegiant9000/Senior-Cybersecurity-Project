"""Tests for org membership invite acceptance and same-org access boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


def _claims(email: str, *, verified: bool = True) -> dict:
    return {
        "uid": "fake-uid",
        "email": email,
        "email_verified": verified,
        "firebase": {"sign_in_provider": "password"},
    }


def _invite_repo(email: str) -> MagicMock:
    repo = MagicMock()
    repo.get_by_token_for_update = AsyncMock(
        return_value=SimpleNamespace(
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email=email,
            org_id=1,
            role="member",
        )
    )
    repo.get_active_membership = AsyncMock(return_value=None)
    repo.create_membership = AsyncMock()
    repo.mark_accepted = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_accept_invite_token_email_mismatch_forbidden(client: AsyncClient):
    """A verified token for another address than the account's is refused before any lookup."""
    repo = _invite_repo("member@example.com")
    app.dependency_overrides[get_invite_repo] = lambda: repo
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        with patch(
            "firebase_admin.auth.verify_id_token",
            return_value=_claims("someone-else@example.com"),
        ):
            resp = await client.post("/api/v1/invites/fake-token/accept")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Signed-in email does not match this account"
    assert "WWW-Authenticate" not in resp.headers
    repo.create_membership.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_invite_unverified_forbidden(client: AsyncClient):
    """An unverified token cannot accept an invite, even for the account's own address."""
    repo = _invite_repo("member@example.com")
    app.dependency_overrides[get_invite_repo] = lambda: repo
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        with patch(
            "firebase_admin.auth.verify_id_token",
            return_value=_claims("member@example.com", verified=False),
        ):
            resp = await client.post("/api/v1/invites/fake-token/accept")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Email address not verified"
    assert "WWW-Authenticate" not in resp.headers
    repo.get_by_token_for_update.assert_not_awaited()
    repo.create_membership.assert_not_awaited()


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
        with patch(
            "firebase_admin.auth.verify_id_token",
            return_value=_claims("member@example.com"),
        ):
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
        with patch(
            "firebase_admin.auth.verify_id_token",
            return_value=_claims("outsider@example.com"),
        ):
            resp = await client.post("/api/v1/invites/fake-token/accept")
    finally:
        app.dependency_overrides.pop(get_invite_repo, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "This invite was sent to a different email address"
    repo.create_membership.assert_not_awaited()
    repo.mark_accepted.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_members_same_org_allowed(client: AsyncClient):
    repo = MagicMock()
    repo.list_members_with_users = AsyncMock(
        return_value=(
            [
                (
                    SimpleNamespace(
                        user_id=1,
                        role="member",
                        status="active",
                        created_at=datetime(2024, 1, 1, tzinfo=UTC),
                    ),
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


@pytest.mark.asyncio
async def test_update_member_role_requires_org_admin(client: AsyncClient):
    async def _member_membership():
        return SimpleNamespace(role="member", org_id=1, status="active")

    app.dependency_overrides[require_same_org_membership] = _member_membership
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        resp = await client.patch("/api/v1/orgs/1/members/101", json={"role": "admin"})
    finally:
        app.dependency_overrides.pop(require_same_org_membership, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_remove_member_requires_org_admin(client: AsyncClient):
    async def _member_membership():
        return SimpleNamespace(role="member", org_id=1, status="active")

    app.dependency_overrides[require_same_org_membership] = _member_membership
    app.dependency_overrides[get_current_user] = _fake_member_user
    try:
        resp = await client.delete("/api/v1/orgs/1/members/101")
    finally:
        app.dependency_overrides.pop(require_same_org_membership, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
