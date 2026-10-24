"""Request-body caps (T-PLAT-06): per-route limits, streaming cap, pre-read file check."""

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import annotated_types
import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from starlette.datastructures import UploadFile

from app.core.body_limit import (
    MULTIPART_OVERHEAD_BYTES,
    REQUEST_TOO_LARGE,
    BodySizeLimitMiddleware,
    limit_for,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal
from app.db.org_upload import OrgUpload
from app.main import app
from app.schemas.agent_scan import (
    AgentScanPayload,
    ScanHost,
    ScanPort,
    ScanService,
    ScanSoftware,
)

_ORG = 1
_P = settings.API_PREFIX
_AGENT_PATH = f"{_P}/inventory/scans"
_EVENTS = f"{_P}/analytics/events"
_FILE_PATHS = [
    f"{_P}/organizations/{{org_id}}/uploads",
    f"{_P}/organizations/{{org_id}}/vendors/import",
    f"{_P}/organizations/{{org_id}}/vendors/import/preview",
    f"{_P}/organizations/{{org_id}}/inventory/uploads/csv/preview",
    f"{_P}/organizations/{{org_id}}/inventory/uploads/csv/import",
]
_AUTH = {"Authorization": "Bearer fake-test-token"}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()


def _file_limit() -> int:
    return settings.MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES


def test_limit_for_routes():
    assert limit_for(_AGENT_PATH) == settings.MAX_AGENT_UPLOAD_BYTES
    for template in _FILE_PATHS:
        assert limit_for(template.format(org_id=1)) == _file_limit(), template
    assert limit_for(f"{_P}/organizations/1/uploads/9") == settings.MAX_JSON_BODY_BYTES
    assert limit_for(_EVENTS) == settings.MAX_JSON_BODY_BYTES


def _is_upload_field(field) -> bool:
    annotation = getattr(field.field_info, "annotation", None)
    return isinstance(annotation, type) and issubclass(annotation, UploadFile)


def test_every_file_route_gets_the_file_limit():
    upload_paths = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.dependant.body_params:
            continue
        path = re.sub(r"\{[^}]*\}", "1", route.path)
        if any(_is_upload_field(f) for f in route.dependant.body_params):
            upload_paths.append(path)
            assert limit_for(path) == _file_limit(), route.path
        elif path != _AGENT_PATH:
            assert limit_for(path) == settings.MAX_JSON_BODY_BYTES, route.path
    assert len(upload_paths) >= len(_FILE_PATHS), upload_paths


async def test_declared_oversize_body_is_refused_unread():
    ran = []
    received = []
    sent = []

    async def stub_app(scope, receive, send):
        ran.append(True)

    async def receive():
        received.append(True)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": _EVENTS,
        "headers": [(b"content-length", str(settings.MAX_JSON_BODY_BYTES + 1).encode())],
    }
    await BodySizeLimitMiddleware(stub_app)(scope, receive, send)

    assert received == []
    assert ran == []
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"]) == {"detail": REQUEST_TOO_LARGE}


async def test_json_body_over_default_limit_is_413(client: AsyncClient):
    resp = await client.post(
        _EVENTS,
        content=b" " * (settings.MAX_JSON_BODY_BYTES + 1),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}


async def test_json_body_at_default_limit_is_not_413(client: AsyncClient):
    event = b'{"event_type":"dashboard_first_view"}'
    body = event + b" " * (settings.MAX_JSON_BODY_BYTES - len(event))
    assert len(body) == settings.MAX_JSON_BODY_BYTES
    resp = await client.post(_EVENTS, content=body, headers={"content-type": "application/json"})
    assert resp.status_code != 413, resp.text


_FILE_PART_HEAD = (
    b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\n'
    b"Content-Type: application/pdf\r\n\r\n%PDF"
)


async def _chunks(
    first: bytes, filler: bytes, chunk: int, total: int, yielded: list[int]
) -> AsyncIterator[bytes]:
    """`first`, then `chunk`-sized pieces of `filler` up to `total` bytes; counts what it yields."""
    yielded.append(len(first))
    yield first
    sent = len(first)
    while sent < total:
        piece = (filler * chunk)[:chunk]
        yielded.append(len(piece))
        yield piece
        sent += len(piece)


@pytest.mark.parametrize(
    ("target", "content_type", "first", "filler"),
    [
        pytest.param(_EVENTS, "application/json", b"{", b" ", id="default-route"),
        pytest.param(
            f"{_P}/organizations/{_ORG}/uploads",
            "multipart/form-data; boundary=x",
            _FILE_PART_HEAD,
            b"a",
            id="file-route",
        ),
    ],
)
async def test_chunked_body_over_limit_is_413_and_read_stops(
    monkeypatch, target, content_type, first, filler
):
    monkeypatch.setattr(settings, "MAX_JSON_BODY_BYTES", 256 * 1024)
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 256 * 1024)
    seen_headers: list = []

    async def record(request):
        seen_headers.append(dict(request.headers))

    yielded: list[int] = []
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=_AUTH,
        event_hooks={"request": [record]},
    ) as c:
        resp = await c.post(
            target,
            content=_chunks(first, filler, 64 * 1024, 4 * 1024 * 1024, yielded),
            headers={"content-type": content_type},
        )

    assert "content-length" not in seen_headers[0]
    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}
    assert sum(yielded) <= limit_for(target) + 64 * 1024


async def test_file_route_allows_body_above_default_limit(
    client: AsyncClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    fake = MagicMock()
    fake.id = 1
    fake.org_id = _ORG
    fake.uploaded_by = 1
    fake.original_filename = "big.pdf"
    fake.stored_filename = "stored.pdf"
    fake.file_size_bytes = 2 * 1024 * 1024
    fake.content_type = "application/pdf"
    fake.upload_purpose = None
    fake.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    content = b"%PDF" + b"a" * (2 * 1024 * 1024)
    assert len(content) > settings.MAX_JSON_BODY_BYTES
    with (
        patch("app.api.routes.v1.uploads.check_org_access", new=AsyncMock(return_value=None)),
        patch(
            "app.repositories.org_upload.SqlOrgUploadRepository.create",
            new=AsyncMock(return_value=fake),
        ),
    ):
        resp = await client.post(
            f"{_P}/organizations/{_ORG}/uploads",
            files={"file": ("big.pdf", content, "application/pdf")},
        )
    assert resp.status_code == 201, resp.text


_CHECK_ORG = {
    "uploads": "app.api.routes.v1.uploads.check_org_access",
    "vendors-import": "app.api.routes.v1.vendors._check_org_access",
    "vendors-import-preview": "app.api.routes.v1.vendors._check_org_access",
    "inventory-csv-preview": "app.api.routes.v1.inventory.check_org_access",
    "inventory-csv-import": "app.api.routes.v1.inventory.check_org_access",
}
_ROUTES = {
    "uploads": (f"{_P}/organizations/{_ORG}/uploads", "application/pdf", b"%PDF" + b"a" * 4096),
    "vendors-import": (
        f"{_P}/organizations/{_ORG}/vendors/import",
        "text/csv",
        b"vendor_name\n" + b"a\n" * 2048,
    ),
    "vendors-import-preview": (
        f"{_P}/organizations/{_ORG}/vendors/import/preview",
        "text/csv",
        b"vendor_name\n" + b"a\n" * 2048,
    ),
    "inventory-csv-preview": (
        f"{_P}/organizations/{_ORG}/inventory/uploads/csv/preview",
        "text/csv",
        b"hostname\n" + b"a\n" * 2048,
    ),
    "inventory-csv-import": (
        f"{_P}/organizations/{_ORG}/inventory/uploads/csv/import?confirm=true",
        "text/csv",
        b"hostname\n" + b"a\n" * 2048,
    ),
}


@pytest.mark.parametrize("route", list(_ROUTES))
async def test_file_over_upload_cap_is_413_before_read(
    route, client: AsyncClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    reads: list[int] = []
    original_read = UploadFile.read

    async def counting_read(self, *args, **kwargs):
        reads.append(1)
        return await original_read(self, *args, **kwargs)

    monkeypatch.setattr(UploadFile, "read", counting_read)
    url, content_type, content = _ROUTES[route]
    assert len(content) > 1024
    assert len(content) < MULTIPART_OVERHEAD_BYTES  # the middleware passes it
    expected = f"File exceeds maximum size of {1024 / (1024 * 1024):.0f} MB"

    async with AsyncSessionLocal() as session:
        rows_before = (
            await session.execute(select(func.count()).select_from(OrgUpload))
        ).scalar_one()
    with patch(_CHECK_ORG[route], new=AsyncMock(return_value=None)):
        resp = await client.post(url, files={"file": ("f.dat", content, content_type)})

    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": expected}
    assert reads == []
    if route == "uploads":
        async with AsyncSessionLocal() as session:
            rows_after = (
                await session.execute(select(func.count()).select_from(OrgUpload))
            ).scalar_one()
        assert rows_after == rows_before
        assert list(tmp_path.iterdir()) == []


def _max_len(model, field: str) -> int:
    for item in model.model_fields[field].metadata:
        if isinstance(item, annotated_types.MaxLen):
            return item.max_length
    raise AssertionError(f"{model.__name__}.{field} has no MaxLen")


def test_maximal_agent_payload_fits_limit():
    def s(model, field: str) -> str:
        return "a" * _max_len(model, field)

    host = {
        "hostname": s(ScanHost, "hostname"),
        "os_name": s(ScanHost, "os_name"),
        "os_version": s(ScanHost, "os_version"),
        "arch": s(ScanHost, "arch"),
        "ip_address": s(ScanHost, "ip_address"),
    }
    software = {
        "vendor": s(ScanSoftware, "vendor"),
        "product": s(ScanSoftware, "product"),
        "version": s(ScanSoftware, "version"),
    }
    service = {"name": s(ScanService, "name"), "state": s(ScanService, "state")}
    port = {"port": 65535, "protocol": "tcp", "process": s(ScanPort, "process")}
    payload = {
        "schema_version": "1.0",
        "scan_id": s(AgentScanPayload, "scan_id"),
        "nonce": s(AgentScanPayload, "nonce"),
        "scanner_version": s(AgentScanPayload, "scanner_version"),
        "host": host,
        "software": [software] * _max_len(AgentScanPayload, "software"),
        "services": [service] * _max_len(AgentScanPayload, "services"),
        "ports": [port] * _max_len(AgentScanPayload, "ports"),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()

    assert len(body) == 72_351_014
    AgentScanPayload.model_validate_json(body)
    assert len(body) <= settings.MAX_AGENT_UPLOAD_BYTES
