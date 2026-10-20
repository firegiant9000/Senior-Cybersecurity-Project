"""Tests for observability bootstrap (Sentry)."""

import sentry_sdk

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
        assert sentry_sdk.get_client().is_active()
    finally:
        sentry_sdk.init()  # no DSN: disables the client for other tests
