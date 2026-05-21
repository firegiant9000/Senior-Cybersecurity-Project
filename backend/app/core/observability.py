"""Observability — Sentry initialization and request-correlation middleware.

This module is intentionally tolerant of a missing sentry-sdk package and an
empty SENTRY_DSN: both produce a silent no-op so local dev / CI never depend
on Sentry being installed or configured.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging import bind_request_context, request_id_ctx

_log = logging.getLogger(__name__)

# Header names accepted as the inbound correlation ID. First match wins.
_INBOUND_REQUEST_ID_HEADERS = ("x-request-id", "x-correlation-id")
_OUTBOUND_REQUEST_ID_HEADER = "x-request-id"

# Keys whose values must be redacted from any Sentry event before leaving the
# process. Match is substring + case-insensitive against both event dict paths
# and breadcrumb data.
_SENSITIVE_KEY_PATTERNS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "email",
    "hostname",
    "host_name",
)
_REDACTED = "[redacted]"

# Best-effort: strip email addresses out of free-form strings.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _scrub(obj: Any) -> Any:
    """Recursively redact sensitive keys and email-looking strings."""
    if isinstance(obj, dict):
        scrubbed: dict[str, Any] = {}
        for k, v in obj.items():
            key_lc = str(k).lower()
            if any(pat in key_lc for pat in _SENSITIVE_KEY_PATTERNS):
                scrubbed[k] = _REDACTED
            else:
                scrubbed[k] = _scrub(v)
        return scrubbed
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(v) for v in obj)
    if isinstance(obj, str):
        return _EMAIL_RE.sub(_REDACTED, obj)
    return obj


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Sentry before_send hook — scrub PII and tag the request_id."""
    try:
        scrubbed = _scrub(event)
        rid = request_id_ctx.get()
        if rid:
            scrubbed.setdefault("tags", {})["request_id"] = rid
        return scrubbed
    except Exception:  # noqa: BLE001 - never block error reporting
        _log.exception("sentry before_send scrubber failed; dropping event")
        return None


def init_sentry() -> bool:
    """Initialize Sentry if SENTRY_DSN is set and sentry-sdk is installed.

    Returns True if Sentry was initialized, False otherwise. Failures are
    swallowed — the app must boot even if observability is unavailable.
    """
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        _log.info("SENTRY_DSN not set — skipping Sentry init")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        _log.warning("sentry-sdk not installed; install it to enable error reporting")
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.SENTRY_ENVIRONMENT or settings.APP_ENV,
            release=settings.SENTRY_RELEASE or None,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,  # never send IPs / user identifiers automatically
            integrations=[
                StarletteIntegration(),
                FastApiIntegration(),
                AsyncioIntegration(),
            ],
            before_send=_before_send,
        )
        _log.info("Sentry initialized (env=%s)", settings.SENTRY_ENVIRONMENT or settings.APP_ENV)
        return True
    except Exception:  # noqa: BLE001
        _log.exception("Sentry init failed; continuing without error reporting")
        return False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request and bind it to logging context.

    Honors an inbound X-Request-ID / X-Correlation-ID header if present (for
    upstream proxies / load tests); otherwise generates a UUID4. The value is
    echoed back on the response so callers can correlate.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        rid = ""
        for header in _INBOUND_REQUEST_ID_HEADERS:
            value = request.headers.get(header)
            if value:
                rid = value[:128]  # cap; protects logs/Sentry from absurd values
                break
        if not rid:
            rid = uuid.uuid4().hex

        bind_request_context(request_id=rid)
        request.state.request_id = rid

        response = await call_next(request)
        response.headers[_OUTBOUND_REQUEST_ID_HEADER] = rid
        return response
