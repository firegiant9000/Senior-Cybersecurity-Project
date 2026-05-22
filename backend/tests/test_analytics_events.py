"""Tests for the activation analytics endpoint (Month 2 Phase F4)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.api.routes.v1 import analytics as analytics_route


@pytest.mark.asyncio
async def test_record_event_rejects_unknown_event_type(client: AsyncClient):
    resp = await client.post(
        "/api/v1/analytics/events",
        json={"event_type": "not_in_allowlist"},
    )
    assert resp.status_code == 400
    assert "Unknown event_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_record_event_rejects_oversized_payload(client: AsyncClient):
    payload = {f"k{i}": i for i in range(analytics_route._MAX_PAYLOAD_KEYS + 1)}
    resp = await client.post(
        "/api/v1/analytics/events",
        json={"event_type": "dashboard_first_view", "payload": payload},
    )
    assert resp.status_code == 400
    assert "too many keys" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_record_event_scrubs_payload_before_persisting(client: AsyncClient):
    captured: dict[str, object] = {}

    def _add(event):
        captured["event"] = event

    async def _refresh(event):
        event.id = 1234

    fake_session = AsyncMock()
    fake_session.add = _add
    fake_session.commit = AsyncMock(return_value=None)
    fake_session.refresh = AsyncMock(side_effect=_refresh)

    from unittest.mock import MagicMock

    from app.api.routes.v1.auth import get_current_user
    from app.db.engine import get_session
    from app.db.user import User
    from app.main import app

    async def _override():
        yield fake_session

    async def _user_override():
        u = MagicMock(spec=User)
        u.id = 1
        u.email = "test@example.com"
        u.role = "admin"
        u.org_id = 7
        u.is_active = True
        return u

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_current_user] = _user_override
    try:
        resp = await client.post(
            "/api/v1/analytics/events",
            json={
                "event_type": "csv_upload_completed",
                "org_id": 7,
                "payload": {
                    "scan_run_id": 99,
                    "user_email": "leak@example.com",
                },
            },
        )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["event_type"] == "csv_upload_completed"

    persisted = captured["event"]
    assert persisted.event_type == "csv_upload_completed"
    assert persisted.org_id == 7
    # email key is scrubbed (the scrubber matches "email" substring)
    assert persisted.payload["user_email"] == "[redacted]"
    # Non-sensitive keys survive
    assert persisted.payload["scan_run_id"] == 99


@pytest.mark.asyncio
async def test_allowed_event_types_match_client_contract():
    """Backend allow-list must include every event the frontend logger emits."""
    expected = {
        "intake_step_skipped",
        "csv_upload_started",
        "csv_upload_completed",
        "m365_connect_started",
        "m365_connect_completed",
        "dashboard_first_view",
    }
    assert analytics_route.ALLOWED_EVENT_TYPES == expected
