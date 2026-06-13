"""Tests for the M365 / Entra OAuth spike (Month 2 Phase E).

Covers: feature-flag gating, state-token issuance and validation, callback
end-to-end with the Graph token exchange mocked, and the sync path's
device-listing behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.db.asset import Asset
from app.db.asset_finding import AssetFinding
from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal
from app.db.integration_credential import IntegrationCredential
from app.db.oauth_state import OAuthState
from app.db.organization import Organization
from app.db.scan_run import ScanRun
from app.db.user import User
from app.integrations import m365 as graph
from app.main import app

PROVIDER = "m365"


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


@pytest.fixture
def _m365_enabled(monkeypatch):
    """Turn the spike on with a freshly generated Fernet key."""
    monkeypatch.setattr(settings, "ENABLE_M365_INTEGRATION", True)
    monkeypatch.setattr(settings, "M365_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "M365_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings, "M365_REDIRECT_URI", "http://test/api/v1/integrations/m365/callback"
    )
    monkeypatch.setattr(settings, "M365_FERNET_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://frontend.test")
    yield


@pytest_asyncio.fixture
async def admin_org():
    """Seed an admin user + org and clean up after the test."""
    async with AsyncSessionLocal() as session:
        org = Organization(name=_unique("M365Org"))
        session.add(org)
        await session.flush()

        admin = User(
            email=f"{_unique('admin')}@example.com",
            firebase_uid=_unique("uid"),
            role="admin",
            org_id=org.id,
            org_role="owner",
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        await session.refresh(org)
        yield admin, org

        await session.execute(
            IntegrationCredential.__table__.delete().where(IntegrationCredential.org_id == org.id)
        )
        await session.execute(OAuthState.__table__.delete().where(OAuthState.org_id == org.id))
        # Sync now persists devices as assets/scan_runs — clean them up FK-first
        # so the org delete below doesn't hit a constraint.
        await session.execute(AssetFinding.__table__.delete().where(AssetFinding.org_id == org.id))
        await session.execute(
            AssetSoftware.__table__.delete().where(AssetSoftware.org_id == org.id)
        )
        await session.execute(Asset.__table__.delete().where(Asset.org_id == org.id))
        await session.execute(ScanRun.__table__.delete().where(ScanRun.org_id == org.id))
        await session.execute(User.__table__.delete().where(User.id == admin.id))
        await session.execute(Organization.__table__.delete().where(Organization.id == org.id))
        await session.commit()


def _override_user(user: User) -> None:
    async def _resolve():
        return user

    app.dependency_overrides[get_current_user] = _resolve


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_status_reports_disabled_when_flag_off(client: AsyncClient, admin_org, monkeypatch):
    admin, org = admin_org
    monkeypatch.setattr(settings, "ENABLE_M365_INTEGRATION", False)
    _override_user(admin)
    try:
        resp = await client.get(f"/api/v1/integrations/m365?org_id={org.id}")
    finally:
        _clear_override()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"enabled": False, "connection": {"connected": False}}


@pytest.mark.asyncio
async def test_consent_is_503_when_disabled(client: AsyncClient, admin_org, monkeypatch):
    admin, org = admin_org
    monkeypatch.setattr(settings, "ENABLE_M365_INTEGRATION", False)
    _override_user(admin)
    try:
        resp = await client.post(f"/api/v1/integrations/m365/consent?org_id={org.id}")
    finally:
        _clear_override()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_consent_issues_state_and_authorize_url(
    client: AsyncClient, admin_org, _m365_enabled
):
    admin, org = admin_org
    _override_user(admin)
    try:
        resp = await client.post(f"/api/v1/integrations/m365/consent?org_id={org.id}")
    finally:
        _clear_override()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["authorize_url"].startswith(settings.M365_AUTHORITY)
    assert "client_id=test-client-id" in body["authorize_url"]
    assert body["state"] in body["authorize_url"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthState).where(OAuthState.state_token == body["state"])
        )
        state_row = result.scalar_one_or_none()
        assert state_row is not None
        assert state_row.org_id == org.id
        assert state_row.user_id == admin.id


@pytest.mark.asyncio
async def test_callback_rejects_forged_state(client: AsyncClient, _m365_enabled):
    resp = await client.get(
        "/api/v1/integrations/m365/callback?code=abc&state=does-not-exist",
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.text or "expired" in resp.text.lower()


@pytest.mark.asyncio
async def test_callback_rejects_expired_state(client: AsyncClient, admin_org, _m365_enabled):
    _, org = admin_org
    # Seed an already-expired state row.
    async with AsyncSessionLocal() as session:
        row = OAuthState(
            org_id=org.id,
            user_id=(await session.execute(select(User).limit(1))).scalar_one().id,
            provider=PROVIDER,
            state_token="expired-state-token",
            redirect_uri=settings.M365_REDIRECT_URI,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        session.add(row)
        await session.commit()

    resp = await client.get(
        "/api/v1/integrations/m365/callback?code=abc&state=expired-state-token",
        follow_redirects=False,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_persists_encrypted_credentials(
    client: AsyncClient, admin_org, _m365_enabled
):
    admin, org = admin_org
    _override_user(admin)
    try:
        consent = await client.post(f"/api/v1/integrations/m365/consent?org_id={org.id}")
    finally:
        _clear_override()
    state = consent.json()["state"]

    token = graph.TokenResponse(
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        expires_in=3600,
        scope="Device.Read.All offline_access",
        tenant_id="tenant-abc",
        account_label="admin@contoso.com",
    )
    with patch(
        "app.api.routes.v1.integrations.graph.exchange_code_for_token",
        AsyncMock(return_value=token),
    ):
        resp = await client.get(
            f"/api/v1/integrations/m365/callback?code=fake-code&state={state}",
            follow_redirects=False,
        )
    assert resp.status_code in (302, 307), resp.text
    assert "m365=connected" in resp.headers["location"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.org_id == org.id,
                IntegrationCredential.provider == PROVIDER,
            )
        )
        cred = result.scalar_one_or_none()
        assert cred is not None
        assert cred.tenant_id == "tenant-abc"
        assert cred.account_label == "admin@contoso.com"
        # Tokens must be encrypted at rest.
        assert cred.access_token_encrypted not in (None, "access-xyz")
        assert cred.refresh_token_encrypted not in (None, "refresh-xyz")
        decrypted = Fernet(settings.M365_FERNET_KEY.encode()).decrypt(
            cred.access_token_encrypted.encode()
        )
        assert decrypted == b"access-xyz"

    # State token must be single-use.
    async with AsyncSessionLocal() as session:
        leftover = await session.execute(select(OAuthState).where(OAuthState.state_token == state))
        assert leftover.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sync_lists_devices_and_updates_payload(
    client: AsyncClient, admin_org, _m365_enabled
):
    admin, org = admin_org

    # Seed an already-connected credential row so sync has something to refresh.
    fernet = Fernet(settings.M365_FERNET_KEY.encode())
    async with AsyncSessionLocal() as session:
        cred = IntegrationCredential(
            org_id=org.id,
            connected_by_user_id=admin.id,
            provider=PROVIDER,
            status="active",
            tenant_id="tenant-abc",
            account_label="admin@contoso.com",
            access_token_encrypted=fernet.encrypt(b"old-access").decode("ascii"),
            refresh_token_encrypted=fernet.encrypt(b"old-refresh").decode("ascii"),
            access_token_expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
        session.add(cred)
        await session.commit()

    refreshed = graph.TokenResponse(
        access_token="fresh-access",
        refresh_token="rotated-refresh",
        expires_in=3600,
        scope="Device.Read.All offline_access",
        tenant_id="tenant-abc",
        account_label="admin@contoso.com",
    )
    devices = [
        graph.ManagedDevice(
            device_id="d1",
            hostname="LAPTOP-01",
            os_name="Windows",
            os_version="10.0.19045",
            last_sync_at="2026-05-22T00:00:00Z",
            compliance_state="compliant",
            raw={"id": "d1"},
        ),
        graph.ManagedDevice(
            device_id="d2",
            hostname="LAPTOP-02",
            os_name="macOS",
            os_version="14.4",
            last_sync_at="2026-05-22T00:00:00Z",
            compliance_state="compliant",
            raw={"id": "d2"},
        ),
    ]

    _override_user(admin)
    try:
        with (
            patch(
                "app.api.routes.v1.integrations.graph.refresh_access_token",
                AsyncMock(return_value=refreshed),
            ),
            patch(
                "app.api.routes.v1.integrations.graph.list_managed_devices",
                AsyncMock(return_value=devices),
            ),
            # Keep the test deterministic — assert the synchronous asset
            # persistence; the background matcher is exercised in its own tests.
            patch(
                "app.workers.matcher_job.run_matcher_for_org",
                AsyncMock(return_value=0),
            ),
        ):
            resp = await client.post(f"/api/v1/integrations/m365/sync?org_id={org.id}")
    finally:
        _clear_override()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["device_count"] == 2
    assert body["scan_run_id"] is not None

    # Devices were persisted as assets under an m365 scan_run (#124).
    async with AsyncSessionLocal() as session:
        assets = (
            (await session.execute(select(Asset).where(Asset.org_id == org.id))).scalars().all()
        )
        assert {a.hostname for a in assets} == {"LAPTOP-01", "LAPTOP-02"}
        assert all(a.discovered_via == "m365" for a in assets)
        scan_run = (
            await session.execute(select(ScanRun).where(ScanRun.id == body["scan_run_id"]))
        ).scalar_one()
        assert scan_run.source == "m365"
        assert scan_run.status == "succeeded"
        assert scan_run.asset_count == 2

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.org_id == org.id,
                IntegrationCredential.provider == PROVIDER,
            )
        )
        cred = result.scalar_one()
        assert cred.last_sync_status == "succeeded"
        assert cred.last_sync_payload is not None
        assert cred.last_sync_payload["device_count"] == 2
        assert len(cred.last_sync_payload["sample"]) == 2
        # Tokens rotated and re-encrypted.
        decrypted = fernet.decrypt(cred.access_token_encrypted.encode()).decode()
        assert decrypted == "fresh-access"


@pytest.mark.asyncio
async def test_sync_404_when_not_connected(client: AsyncClient, admin_org, _m365_enabled):
    admin, org = admin_org
    _override_user(admin)
    try:
        resp = await client.post(f"/api/v1/integrations/m365/sync?org_id={org.id}")
    finally:
        _clear_override()
    assert resp.status_code == 404
