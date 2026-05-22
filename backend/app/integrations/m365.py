"""Microsoft Graph client for the M365 / Entra OAuth spike (Phase E5).

Thin wrapper around the OAuth code+token exchange and the
``/deviceManagement/managedDevices`` endpoint. Production hardening
(retry/backoff beyond one attempt, app-only auth, change-notifications)
is deferred to Month 3 — see docs/m365_integration_notes.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = (
    "Device.Read.All",
    "DeviceManagementManagedDevices.Read.All",
    "User.Read",
    "offline_access",
)
# Constant tenant id Microsoft uses for personal MSAs — rejected because
# managedDevices only exists for organizational tenants.
PERSONAL_MSA_TID = "9188040d-6c67-4c5b-b112-36a304b66dad"


@dataclass(slots=True)
class TokenResponse:
    """Parsed OAuth token-endpoint response."""

    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str
    tenant_id: str | None
    account_label: str | None


@dataclass(slots=True)
class ManagedDevice:
    """Subset of a Graph managedDevice we map to an asset row."""

    device_id: str
    hostname: str | None
    os_name: str | None
    os_version: str | None
    last_sync_at: str | None
    compliance_state: str | None
    raw: dict[str, Any]


def build_authorize_url(
    *,
    authority: str,
    client_id: str,
    redirect_uri: str,
    state_token: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
) -> str:
    """Build the Microsoft authorize URL for the consent step."""
    from urllib.parse import urlencode

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(scopes),
        "state": state_token,
        "prompt": "select_account",
    }
    return f"{authority.rstrip('/')}/oauth2/v2.0/authorize?{urlencode(params)}"


def _parse_id_token_tid(id_token: str | None) -> str | None:
    """Best-effort tenant id extraction from an ID token without verification.

    The token is freshly minted by Microsoft and we hit it over TLS — for the
    spike we just need the ``tid`` to label the connection. Full verification
    is Month 3.
    """
    if not id_token:
        return None
    try:
        import base64
        import json

        payload = id_token.split(".")[1]
        # JWT base64url payload without padding
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded)
        tid = claims.get("tid")
        return str(tid) if tid else None
    except (ValueError, IndexError, json.JSONDecodeError) as exc:  # noqa: F821
        logger.debug("id_token tid parse failed: %s", exc)
        return None


def _account_label_from_id_token(id_token: str | None) -> str | None:
    if not id_token:
        return None
    try:
        import base64
        import json

        payload = id_token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload + padding))
        return (
            claims.get("preferred_username")
            or claims.get("upn")
            or claims.get("email")
            or claims.get("name")
        )
    except (ValueError, IndexError, json.JSONDecodeError):  # noqa: F821
        return None


async def exchange_code_for_token(
    *,
    authority: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    http_client: httpx.AsyncClient | None = None,
) -> TokenResponse:
    """Exchange an authorization code for access + refresh tokens."""
    url = f"{authority.rstrip('/')}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "scope": " ".join(scopes),
    }
    client = http_client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.post(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()
        body = resp.json()
    finally:
        if http_client is None:
            await client.aclose()

    id_token = body.get("id_token")
    return TokenResponse(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_in=int(body.get("expires_in", 3600)),
        scope=body.get("scope", ""),
        tenant_id=_parse_id_token_tid(id_token),
        account_label=_account_label_from_id_token(id_token),
    )


async def refresh_access_token(
    *,
    authority: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    http_client: httpx.AsyncClient | None = None,
) -> TokenResponse:
    """Exchange a refresh token for a fresh access token."""
    url = f"{authority.rstrip('/')}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(scopes),
    }
    client = http_client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.post(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()
        body = resp.json()
    finally:
        if http_client is None:
            await client.aclose()

    id_token = body.get("id_token")
    return TokenResponse(
        access_token=body["access_token"],
        # Microsoft may rotate the refresh token — keep the new one if present.
        refresh_token=body.get("refresh_token") or refresh_token,
        expires_in=int(body.get("expires_in", 3600)),
        scope=body.get("scope", ""),
        tenant_id=_parse_id_token_tid(id_token),
        account_label=_account_label_from_id_token(id_token),
    )


def _map_managed_device(raw: dict[str, Any]) -> ManagedDevice:
    return ManagedDevice(
        device_id=str(raw.get("id") or ""),
        hostname=raw.get("deviceName") or raw.get("computerName"),
        os_name=raw.get("operatingSystem"),
        os_version=raw.get("osVersion"),
        last_sync_at=raw.get("lastSyncDateTime"),
        compliance_state=raw.get("complianceState"),
        raw=raw,
    )


async def list_managed_devices(
    *,
    access_token: str,
    page_size: int = 100,
    http_client: httpx.AsyncClient | None = None,
    max_pages: int = 50,
) -> list[ManagedDevice]:
    """Page through ``deviceManagement/managedDevices``.

    Honours ``Retry-After`` on a single 429 per page; aborts on the second.
    Returns whatever was collected so far on partial failure — callers
    decide whether to mark the scan_run as ``partial`` or ``failed``.
    """
    client = http_client or httpx.AsyncClient(timeout=30.0)
    url: str | None = f"{GRAPH_BASE_URL}/deviceManagement/managedDevices?$top={page_size}"
    collected: list[ManagedDevice] = []
    headers = {"Authorization": f"Bearer {access_token}"}
    pages = 0
    consecutive_429 = 0
    try:
        while url and pages < max_pages:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 429:
                consecutive_429 += 1
                if consecutive_429 > 1:
                    logger.warning("Graph throttled twice in a row; aborting page loop")
                    break
                retry_after = float(resp.headers.get("Retry-After", "1"))
                await asyncio.sleep(min(retry_after, 30.0))
                continue
            consecutive_429 = 0
            if resp.status_code == 403:
                # Tenant likely lacks Intune licensing — treat as empty list.
                logger.info("Graph managedDevices 403 — likely no Intune; returning empty")
                return collected
            resp.raise_for_status()
            body = resp.json()
            for raw in body.get("value", []):
                if isinstance(raw, dict):
                    collected.append(_map_managed_device(raw))
            url = body.get("@odata.nextLink")
            pages += 1
    finally:
        if http_client is None:
            await client.aclose()
    return collected
