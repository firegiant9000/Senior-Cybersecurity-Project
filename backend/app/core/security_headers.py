"""Security headers on every API response (T-PLAT-01), as a pure ASGI middleware.

It is the OUTERMOST middleware, so errors, CORS preflights and the 413 from the body limit all
carry the headers. A header a route already set is never overwritten.
"""

from fastapi import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HSTS = "max-age=31536000; includeSubDomains"
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'unsafe-inline' https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/ "
    "https://cdn.jsdelivr.net/npm/redoc@2/; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/ "
    "https://cdn.jsdelivr.net/npm/redoc@2/ https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; worker-src blob:; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'"
)


def security_headers(path: str, docs_paths: frozenset[str]) -> dict[str, str]:
    return {
        "Strict-Transport-Security": HSTS,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": DOCS_CSP if path in docs_paths else API_CSP,
    }


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, docs_paths: frozenset[str]) -> None:
        self.app = app
        self.docs_paths = docs_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        extra = security_headers(scope["path"], self.docs_paths)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                for name, value in extra.items():
                    if name.lower().encode("latin-1") not in present:
                        headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def internal_error_response(request: Request, docs_paths: frozenset[str]) -> PlainTextResponse:
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers=security_headers(request.url.path, docs_paths),
    )
