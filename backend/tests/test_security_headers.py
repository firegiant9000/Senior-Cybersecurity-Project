"""API security headers (T-PLAT-01): every response, including errors, preflights and docs."""

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security_headers import (
    API_CSP,
    DOCS_CSP,
    SecurityHeadersMiddleware,
    security_headers,
)
from app.db.engine import get_session
from app.main import app

_P = settings.API_PREFIX
EXPECTED = security_headers("/x", frozenset())


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()


def assert_headers(resp, csp: str = API_CSP) -> None:
    for name, value in EXPECTED.items():
        if name == "Content-Security-Policy":
            value = csp
        assert resp.headers.get(name) == value, name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "kwargs", "status", "use_client"),
    [
        ("GET", "/health", {}, 200, False),
        ("GET", f"{_P}/auth/me", {}, 401, False),
        ("GET", "/no-such-path", {}, 404, False),
        ("POST", f"{_P}/analytics/events", {"json": {"event": 1}}, 422, True),
        (
            "OPTIONS",
            f"{_P}/health",
            {
                "headers": {
                    "Origin": "https://example.test",
                    "Access-Control-Request-Method": "GET",
                }
            },
            None,
            False,
        ),
    ],
    ids=["health-200", "auth-401", "not-found-404", "validation-422", "preflight"],
)
async def test_api_headers_on_representative_responses(
    client, anon_client, method, path, kwargs, status, use_client
):
    c = client if use_client else anon_client
    resp = await c.request(method, path, **kwargs)
    if status is not None:
        assert resp.status_code == status
    elif method == "OPTIONS":
        assert resp.status_code in (200, 400)
    assert_headers(resp)


@pytest.mark.asyncio
async def test_headers_on_413(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_JSON_BODY_BYTES", 1024)
    resp = await anon_client.post(
        f"{_P}/analytics/events",
        content=b"x" * 2048,
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413
    assert_headers(resp)


@pytest.mark.asyncio
async def test_headers_on_unhandled_500():
    async def _boom():
        raise RuntimeError("boom-secret")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = _boom
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as c:
            resp = await c.get(f"{_P}/public/stats")
        assert resp.status_code == 500
        assert resp.text == "Internal Server Error"
        assert "boom-secret" not in resp.text
        assert_headers(resp)

        # ServerErrorMiddleware still re-raises, so logging and Sentry see the exception.
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=True),
            base_url="http://test",
        ) as c:
            with pytest.raises(RuntimeError, match="boom-secret"):
                await c.get(f"{_P}/public/stats")
    finally:
        app.dependency_overrides.pop(get_session, None)
        limiter.reset()


@pytest.mark.asyncio
async def test_docs_pages_get_the_docs_csp(anon_client):
    for path in ("/docs", "/redoc", app.swagger_ui_oauth2_redirect_url):
        resp = await anon_client.get(path)
        assert resp.status_code == 200
        assert_headers(resp, csp=DOCS_CSP)


def _directives(csp: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in csp.split(";"):
        tokens = part.split()
        if tokens:
            out[tokens[0]] = tokens[1:]
    return out


def _allowed(url: str, sources: list[str]) -> bool:
    u = urlparse(url)
    for source in sources:
        if not source.startswith("https://"):
            continue
        s = urlparse(source)
        if (s.scheme, s.netloc) != (u.scheme, u.netloc):
            continue
        if not s.path or u.path.startswith(s.path):
            return True
    return False


_EXTERNAL_URL = re.compile(r"(?:https?:)?//")


class _TagCollector(HTMLParser):
    """Records (lower-cased tag name, decoded attrs) for every start tag."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/docs", "/redoc"])
async def test_docs_csp_allows_the_assets_docs_pages_load(anon_client, path):
    html = (await anon_client.get(path)).text
    directives = _directives(DOCS_CSP)

    parser = _TagCollector()
    parser.feed(html)
    parser.close()

    found: dict[str, list[str]] = {"script": [], "style": [], "icon": []}
    for name, attrs in parser.tags:
        rels = (attrs.get("rel") or "").lower().split()
        for attr_name in ("src", "href"):
            url = attrs.get(attr_name) or ""
            if not _EXTERNAL_URL.match(url):
                continue
            if url.startswith("//"):
                url = "https:" + url
            if name == "script" and attr_name == "src":
                kind, directive = "script", "script-src"
            elif name == "link" and "stylesheet" in rels:
                kind, directive = "style", "style-src"
            elif (name == "link" and "icon" in rels) or name == "img":
                kind, directive = "icon", "img-src"
            else:
                pytest.fail(f"unclassified external URL in <{name}>: {url}")
            found[kind].append(url)
            assert _allowed(url, directives[directive]), url

    assert found["script"], "page loads no external script"
    assert found["style"], "page loads no external stylesheet"
    if path == "/docs":
        assert found["icon"], "/docs loads no icon"

    inline = [attrs for name, attrs in parser.tags if name == "script" and "src" not in attrs]
    if inline:
        assert "'unsafe-inline'" in directives["script-src"]


def test_allowed_helper_is_path_restricted():
    sources = ["https://cdn.jsdelivr.net/npm/redoc@2/", "https://fonts.googleapis.com"]
    assert _allowed("https://cdn.jsdelivr.net/npm/redoc@2/bundles/x.js", sources)
    assert not _allowed("https://cdn.jsdelivr.net/npm/evil@1/x.js", sources)
    assert not _allowed("https://cdn.jsdelivr.net/npm/redoc@2evil/x.js", sources)
    assert not _allowed("https://evil.example/npm/redoc@2/x.js", sources)
    assert not _allowed("https://cdn.jsdelivr.net.evil.com/npm/redoc@2/x.js", sources)
    assert _allowed("https://fonts.googleapis.com/css?family=a", sources)


@pytest.mark.asyncio
async def test_existing_header_not_overwritten():
    async def stub(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"X-Frame-Options", b"SAMEORIGIN")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    sent = []

    async def capture(message):
        sent.append(message)

    mw = SecurityHeadersMiddleware(stub, docs_paths=frozenset())
    await mw({"type": "http", "path": "/x"}, None, capture)
    headers = [(k.decode().lower(), v.decode()) for k, v in sent[0]["headers"]]
    assert [v for k, v in headers if k == "x-frame-options"] == ["SAMEORIGIN"]
    for name, value in EXPECTED.items():
        if name != "X-Frame-Options":
            assert (name.lower(), value) in headers
