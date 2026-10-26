"""Request-body size limit (T-PLAT-06), as a pure ASGI middleware.

It must stay the INNERMOST user middleware (added first in ``create_app``). SlowAPI and
RequestContext are ``BaseHTTPMiddleware``: their ``receive`` runs inside an anyio task group,
so an exception raised in a wrapper outside them reaches FastAPI as an ``ExceptionGroup``
(a 400 or 500) instead of a 413. Innermost, the wrapper raises in the frame that is reading the
body, and the 413 goes out through the normal exception handlers with the usual headers.
"""

import re

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

REQUEST_TOO_LARGE = "Request body too large"
MULTIPART_OVERHEAD_BYTES = 64 * 1024

_FILE_ROUTE = re.compile(
    rf"^{re.escape(settings.API_PREFIX)}/organizations/[^/]+/"
    r"(uploads|vendors/import(/preview)?|inventory/uploads/csv/(preview|import))$"
)


def limit_for(path: str) -> int:
    """The body cap for a request path. Settings are read per call."""
    if path == f"{settings.API_PREFIX}/inventory/scans":
        return settings.MAX_AGENT_UPLOAD_BYTES
    if _FILE_ROUTE.match(path):
        return settings.MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES
    return settings.MAX_JSON_BODY_BYTES


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = limit_for(scope["path"])
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            response = JSONResponse(status_code=413, content={"detail": REQUEST_TOO_LARGE})
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail=REQUEST_TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)
