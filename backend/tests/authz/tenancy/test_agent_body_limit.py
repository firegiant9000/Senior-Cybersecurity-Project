"""Agent scan upload: authenticated before its body is read, size-capped, one large body at a time.

Real token verification throughout (T-PLAT-06). The only patches are lowered limits through
`settings`, and holding or resetting the large-upload slot.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

import pytest
from starlette.requests import Request

from app.api.routes.v1.inventory import (
    AGENT_UPLOAD_BUSY,
    AGENT_UPLOAD_TIMEOUT,
    _reset_agent_upload_slots,
    agent_upload_slot,
)
from app.core.body_limit import REQUEST_TOO_LARGE
from app.core.config import settings
from app.main import app
from tests.authz.tenancy._agents import ACCEPTED, STATUS, UPLOAD, issue_agent, scan_payload
from tests.authz.tenancy._world import snapshot_org

MIB = 1024 * 1024


@pytest.fixture(autouse=True)
def _fresh_slots():
    _reset_agent_upload_slots()
    yield
    _reset_agent_upload_slots()


def _body(world, size: int | None = None) -> bytes:
    raw = json.dumps(scan_payload(world.a), separators=(",", ":")).encode()
    if size is None:
        return raw
    assert len(raw) <= size
    return raw + b" " * (size - len(raw))


async def _stream(
    parts: list[bytes],
    yielded: list[int],
    *,
    filler: bytes = b"",
    filler_chunk: int = 0,
    total: int = 0,
) -> AsyncIterator[bytes]:
    """Yield `parts`, then `filler_chunk`-byte pieces of `filler` until `total` bytes; log sizes."""
    sent = 0
    for part in parts:
        yielded.append(len(part))
        sent += len(part)
        yield part
    while filler_chunk and sent < total:
        piece = (filler * filler_chunk)[:filler_chunk]
        yielded.append(len(piece))
        sent += len(piece)
        yield piece


async def _warm(client, world) -> None:
    """One status call so the token's last-used debounce can't change a later snapshot."""
    resp = await client.get(STATUS[1].format(scan_run_id=world.a.ids["scan_run_id"]))
    assert resp.status_code == 200, resp.text


async def _held_slot():
    request = Request({"type": "http", "headers": []})
    gen = agent_upload_slot(request)
    await anext(gen)
    return gen


async def test_agent_upload_without_token_is_401_before_body_read(world, authz_client):
    client = await authz_client(None)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []

    resp = await client.post(
        UPLOAD[1],
        content=_stream([], yielded, filler=b"a", filler_chunk=MIB, total=8 * MIB),
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 401, resp.text
    assert sum(yielded) <= MIB
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_agent_upload_over_limit_is_413(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * 1024)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await client.post(
        UPLOAD[1], content=_body(world, 64 * 1024 + 1), headers={"content-type": "application/json"}
    )

    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_chunked_agent_upload_over_limit_is_413(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * 1024)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []
    head = _body(world).rstrip()[:-1]  # the JSON minus its closing brace

    resp = await client.post(
        UPLOAD[1],
        content=_stream([head], yielded, filler=b" ", filler_chunk=16 * 1024, total=MIB),
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}
    assert sum(yielded) <= 64 * 1024 + 16 * 1024
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_agent_upload_busy_is_503_unread(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []
    gen = await _held_slot()
    try:
        resp = await client.post(
            UPLOAD[1],
            content=_stream([_body(world)], yielded),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 503, resp.text
        assert resp.json() == {"detail": AGENT_UPLOAD_BUSY}
        assert resp.headers["retry-after"] == "5"
        assert sum(yielded) == 0
        assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    finally:
        await gen.aclose()

    again = await client.post(
        UPLOAD[1],
        content=_stream([_body(world)], []),
        headers={"content-type": "application/json"},
    )
    assert again.status_code == ACCEPTED[UPLOAD], again.text


async def test_small_agent_upload_skips_the_slot(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    gen = await _held_slot()
    try:
        resp = await client.post(
            UPLOAD[1], content=_body(world), headers={"content-type": "application/json"}
        )
    finally:
        await gen.aclose()
    assert resp.status_code == ACCEPTED[UPLOAD], resp.text


async def test_agent_upload_without_token_takes_no_slot(world, authz_client):
    client = await authz_client(None)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    gen = await _held_slot()
    try:
        resp = await client.post(
            UPLOAD[1],
            content=_stream([_body(world)], []),
            headers={"content-type": "application/json"},
        )
    finally:
        await gen.aclose()
    assert resp.status_code == 401, resp.text
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_stalled_agent_upload_times_out_and_frees_the_slot(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_UPLOAD_READ_TIMEOUT_SECONDS", 0.2)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    async def stalled() -> AsyncIterator[bytes]:
        yield b" " * 1024
        await asyncio.sleep(5)
        yield b" "

    started = time.monotonic()
    resp = await client.post(
        UPLOAD[1], content=stalled(), headers={"content-type": "application/json"}
    )

    assert time.monotonic() - started < 2
    assert resp.status_code == 408, resp.text
    assert resp.json() == {"detail": AGENT_UPLOAD_TIMEOUT}
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before

    again = await client.post(
        UPLOAD[1],
        content=_stream([_body(world)], []),
        headers={"content-type": "application/json"},
    )
    assert again.status_code == ACCEPTED[UPLOAD], again.text


async def test_agent_upload_client_disconnect_is_400(world, authz_client):
    issued = await issue_agent(world.a)
    await _warm(await authz_client(issued.raw_token), world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    sent: list[dict] = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": UPLOAD[1],
        "raw_path": UPLOAD[1].encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"authorization", f"Bearer {issued.raw_token}".encode()),
            (b"content-type", b"application/json"),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await app(scope, receive, send)

    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert [m["status"] for m in starts] == [400]
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


async def test_agent_upload_at_limit_is_accepted(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * 1024)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    body = _body(world, 64 * 1024)
    assert len(body) == 64 * 1024

    resp = await client.post(UPLOAD[1], content=body, headers={"content-type": "application/json"})

    assert resp.status_code == ACCEPTED[UPLOAD], resp.text


async def test_agent_upload_invalid_body_keeps_422_shape(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await client.post(UPLOAD[1], json={"schema_version": "1.0"})

    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail
    assert all(item["loc"][0] == "body" for item in detail)
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            json.dumps(
                {"software": [{"vendor": "v" * 200, "product": "p"}] * 50_001},
                separators=(",", ":"),
            ).encode(),
            id="missing-fields-and-list-over-cap",
        ),
        pytest.param(b"{not json", id="json-invalid"),
    ],
)
async def test_agent_422_never_echoes_the_request_body(world, authz_client, body):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await client.post(UPLOAD[1], content=body, headers={"content-type": "application/json"})

    assert resp.status_code == 422, resp.text[:300]
    detail = resp.json()["detail"]
    assert detail
    assert all("input" not in item for item in detail)
    assert all(item["loc"][0] == "body" for item in detail)
    assert len(resp.content) < 10_000
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
