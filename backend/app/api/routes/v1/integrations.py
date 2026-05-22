"""Integrations routes — M365/Entra OAuth spike (Phase E).

Endpoints (all under ``/api/v1/integrations/m365``):

- ``POST .../consent``   — issue a Microsoft consent URL + state token
- ``GET  .../callback``  — finalise the OAuth roundtrip (Microsoft-hosted browser)
- ``POST .../sync``      — pull managed devices into ``last_sync_payload``
- ``GET  .../``          — current connection state for the org

The ``sync`` endpoint stores Graph results on
``integration_credentials.last_sync_payload`` rather than ``assets`` —
Phase A + C3 wire the proper asset insertion. See
docs/m365_integration_notes.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.integration_credential import IntegrationCredential
from app.db.user import User
from app.integrations import m365 as graph
from app.services.m365_oauth import (
    PROVIDER_M365,
    M365NotConfigured,
    consume_state_token,
    decrypt_token,
    encrypt_token,
    issue_state_token,
    require_m365_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/m365", tags=["integrations"])


def _ensure_enabled() -> None:
    """503 when the M365 spike is feature-flagged off."""
    if not settings.ENABLE_M365_INTEGRATION:
        raise HTTPException(
            status_code=503,
            detail="M365 integration is disabled (ENABLE_M365_INTEGRATION=false)",
        )


def _connection_view(cred: IntegrationCredential | None) -> dict[str, Any]:
    if cred is None:
        return {"connected": False}
    return {
        "connected": True,
        "status": cred.status,
        "tenant_id": cred.tenant_id,
        "account_label": cred.account_label,
        "scopes": cred.scopes,
        "last_sync_at": cred.last_sync_at.isoformat() if cred.last_sync_at else None,
        "last_sync_status": cred.last_sync_status,
        "device_count": (
            (cred.last_sync_payload or {}).get("device_count")
            if isinstance(cred.last_sync_payload, dict)
            else None
        ),
    }


@router.get("")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_status(
    request: Request,  # noqa: ARG001
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the M365 connection status for an org (or `enabled=false`)."""
    if not settings.ENABLE_M365_INTEGRATION:
        return {"enabled": False, "connection": {"connected": False}}
    await check_org_access(current_user, org_id, session)
    result = await session.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.org_id == org_id,
            IntegrationCredential.provider == PROVIDER_M365,
        )
    )
    cred = result.scalar_one_or_none()
    return {"enabled": True, "connection": _connection_view(cred)}


@router.post("/consent")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def start_consent(
    request: Request,  # noqa: ARG001
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return a Microsoft consent URL with a fresh state token."""
    _ensure_enabled()
    try:
        require_m365_config()
    except M365NotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    await check_org_access(current_user, org_id, session)

    try:
        state_row = await issue_state_token(
            session,
            org_id=org_id,
            user_id=current_user.id,
            redirect_uri=settings.M365_REDIRECT_URI,
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("Failed to issue M365 state token")
        raise HTTPException(status_code=500, detail="Failed to start consent flow")

    url = graph.build_authorize_url(
        authority=settings.M365_AUTHORITY,
        client_id=settings.M365_CLIENT_ID,
        redirect_uri=settings.M365_REDIRECT_URI,
        state_token=state_row.state_token,
    )
    return {"authorize_url": url, "state": state_row.state_token, "expires_at": state_row.expires_at.isoformat()}


@router.get("/callback")
async def oauth_callback(
    request: Request,  # noqa: ARG001
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Microsoft redirects here after user consent. Validates state, exchanges
    the code, encrypts and stores credentials, then bounces to the frontend.
    """
    _ensure_enabled()
    try:
        require_m365_config()
    except M365NotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    frontend_base = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""

    def _bounce(status: str, message: str = "") -> RedirectResponse:
        from urllib.parse import urlencode

        base = frontend_base or "/integrations"
        target = (
            f"{frontend_base}/integrations?{urlencode({'m365': status, 'message': message})}"
            if frontend_base
            else f"{base}?{urlencode({'m365': status, 'message': message})}"
        )
        return RedirectResponse(url=target)

    if error:
        return _bounce("error", error_description or error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        state_row = await consume_state_token(session, state_token=state)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("Failed to consume M365 state token")
        raise HTTPException(status_code=500, detail="State token lookup failed")

    if state_row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    try:
        token = await graph.exchange_code_for_token(
            authority=settings.M365_AUTHORITY,
            client_id=settings.M365_CLIENT_ID,
            client_secret=settings.M365_CLIENT_SECRET,
            redirect_uri=settings.M365_REDIRECT_URI,
            code=code,
        )
    except httpx.HTTPError as exc:
        logger.exception("M365 token exchange failed")
        return _bounce("error", f"token_exchange_failed: {exc}")

    if token.tenant_id == graph.PERSONAL_MSA_TID:
        return _bounce("error", "personal_msa_unsupported")

    try:
        result = await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.org_id == state_row.org_id,
                IntegrationCredential.provider == PROVIDER_M365,
            )
        )
        cred = result.scalar_one_or_none()
        expires_at = datetime.now(UTC) + timedelta(seconds=max(token.expires_in - 30, 60))
        if cred is None:
            cred = IntegrationCredential(
                org_id=state_row.org_id,
                connected_by_user_id=state_row.user_id,
                provider=PROVIDER_M365,
                status="active",
            )
            session.add(cred)

        cred.status = "active"
        cred.tenant_id = token.tenant_id
        cred.account_label = token.account_label
        cred.scopes = token.scope
        cred.access_token_encrypted = encrypt_token(token.access_token)
        cred.refresh_token_encrypted = encrypt_token(token.refresh_token)
        cred.access_token_expires_at = expires_at
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("Failed to persist M365 credentials")
        return _bounce("error", "persistence_failed")

    return _bounce("connected", token.account_label or "")


@router.post("/sync")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def sync_devices(
    request: Request,  # noqa: ARG001
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Pull managed devices via Graph and stash them on the credential row.

    Phase A + C3 will replace ``last_sync_payload`` with proper ``assets`` /
    ``scan_runs`` writes — the spike just proves the OAuth + Graph path end
    to end.
    """
    _ensure_enabled()
    try:
        require_m365_config()
    except M365NotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    await check_org_access(current_user, org_id, session)

    result = await session.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.org_id == org_id,
            IntegrationCredential.provider == PROVIDER_M365,
        )
    )
    cred = result.scalar_one_or_none()
    if cred is None or not cred.refresh_token_encrypted:
        raise HTTPException(status_code=404, detail="M365 is not connected for this organization")

    try:
        refresh = decrypt_token(cred.refresh_token_encrypted)
    except M365NotConfigured as exc:
        cred.status = "reauth_needed"
        await session.commit()
        raise HTTPException(status_code=401, detail=str(exc))

    try:
        token = await graph.refresh_access_token(
            authority=settings.M365_AUTHORITY,
            client_id=settings.M365_CLIENT_ID,
            client_secret=settings.M365_CLIENT_SECRET,
            refresh_token=refresh,  # type: ignore[arg-type]
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        if status_code == 400:
            cred.status = "reauth_needed"
            await session.commit()
            raise HTTPException(status_code=401, detail="invalid_grant — reconnect required")
        logger.exception("M365 refresh failed")
        raise HTTPException(status_code=502, detail="M365 token refresh failed")
    except httpx.HTTPError:
        logger.exception("M365 refresh failed")
        raise HTTPException(status_code=502, detail="M365 token refresh failed")

    cred.access_token_encrypted = encrypt_token(token.access_token)
    if token.refresh_token:
        cred.refresh_token_encrypted = encrypt_token(token.refresh_token)
    cred.access_token_expires_at = datetime.now(UTC) + timedelta(
        seconds=max(token.expires_in - 30, 60)
    )

    started_at = datetime.now(UTC)
    try:
        devices = await graph.list_managed_devices(access_token=token.access_token)
        status_label = "succeeded"
    except httpx.HTTPError:
        logger.exception("M365 device listing failed")
        devices = []
        status_label = "failed"

    cred.last_sync_at = datetime.now(UTC)
    cred.last_sync_status = status_label
    cred.last_sync_payload = {
        "device_count": len(devices),
        "started_at": started_at.isoformat(),
        "finished_at": cred.last_sync_at.isoformat(),
        "sample": [
            {
                "device_id": d.device_id,
                "hostname": d.hostname,
                "os_name": d.os_name,
                "os_version": d.os_version,
                "compliance_state": d.compliance_state,
            }
            for d in devices[:25]
        ],
    }
    cred.status = "active" if status_label == "succeeded" else cred.status
    await session.commit()

    return {
        "status": status_label,
        "device_count": len(devices),
        "synced_at": cred.last_sync_at.isoformat(),
    }


@router.delete("", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def disconnect(
    request: Request,  # noqa: ARG001
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove the stored credentials for this org."""
    _ensure_enabled()
    await check_org_access(current_user, org_id, session)
    result = await session.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.org_id == org_id,
            IntegrationCredential.provider == PROVIDER_M365,
        )
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="M365 is not connected for this organization")
    await session.delete(cred)
    await session.commit()
    return None
