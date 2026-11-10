"""Tests for observability bootstrap (Sentry)."""

import sentry_sdk
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sentry_sdk.transport import Transport

from app.core.config import settings
from app.core.observability import init_sentry


def test_init_sentry_succeeds(monkeypatch):
    """init_sentry() must really initialise the SDK with the pinned framework stack.

    init_sentry swallows exceptions and returns False, so a broken integration
    (e.g. a missing optional dependency of the Starlette integration) would
    otherwise only surface as a log line in production.
    """
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    try:
        assert init_sentry() is True
        assert "starlette" in sentry_sdk.get_client().integrations
    finally:
        # An explicit empty DSN ignores SENTRY_DSN in the environment, so no
        # later test can report to a real project.
        sentry_sdk.init(dsn="")


async def test_nested_route_transaction_name_keeps_the_prefix(monkeypatch):
    """fastapi 0.162 keeps included routers nested; sentry-sdk before 2.74 then named the
    transaction by the inner path alone, merging routes that share it across routers."""
    names: list[str] = []

    class _Capture(Transport):
        def capture_envelope(self, envelope):
            names.extend(
                i.payload.json["transaction"] for i in envelope.items if i.type == "transaction"
            )

    real_init = sentry_sdk.init
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0)
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: real_init(transport=_Capture(), **kw))
    inner = APIRouter()
    inner.add_api_route("/things/{thing_id}", lambda thing_id: {}, methods=["GET"])
    outer = APIRouter()
    outer.include_router(inner, prefix="/orgs/{org_id}")
    app = FastAPI()
    app.include_router(outer, prefix="/api/v1")
    try:
        assert init_sentry() is True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            assert (await client.get("/api/v1/orgs/1/things/2")).status_code == 200
        sentry_sdk.flush()
    finally:
        monkeypatch.undo()
        sentry_sdk.init(dsn="")
    assert names == ["/api/v1/orgs/{org_id}/things/{thing_id}"]
