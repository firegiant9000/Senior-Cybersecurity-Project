"""Agent scan upload: authenticated before its body is read, size-capped, and bounded in flight.

Real token verification throughout (T-PLAT-06). The only patches are lowered limits and budgets
through `settings`, and occupying or resetting the upload gate. Every upload must declare a
Content-Length (411 otherwise); it is admitted against a process-wide byte budget and a per-org
share, waits a bounded time for room, and no DB connection is held while it waits or reads.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

import pytest

from app.api.routes.v1.inventory import (
    AGENT_UPLOAD_BUSY,
    AGENT_UPLOAD_LENGTH_REQUIRED,
    AGENT_UPLOAD_TIMEOUT,
    _agent_gate,
    _agent_uploads_in_flight,
    _reset_agent_upload_slots,
)
from app.core.body_limit import REQUEST_TOO_LARGE
from app.core.config import Settings, settings
from app.db.engine import engine
from app.main import app
from tests.authz.tenancy._agents import ACCEPTED, STATUS, UPLOAD, issue_agent, scan_payload
from tests.authz.tenancy._world import snapshot_org

MIB = 1024 * 1024
KIB = 1024


@pytest.fixture(autouse=True)
def _fresh_slots():
    _reset_agent_upload_slots()
    yield
    _reset_agent_upload_slots()


def _assert_slots_free() -> None:
    assert _agent_uploads_in_flight() == 0


def _body(org, size: int | None = None) -> bytes:
    raw = json.dumps(scan_payload(org), separators=(",", ":")).encode()
    if size is None:
        return raw
    assert len(raw) <= size
    return raw + b" " * (size - len(raw))


def _headers(body: bytes) -> dict[str, str]:
    return {"content-type": "application/json", "content-length": str(len(body))}


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


async def _fill_budget() -> list[tuple[int, int]]:
    """Occupy the whole process-wide budget with made-up orgs; release with `_free`."""
    held: list[tuple[int, int]] = []
    remaining = settings.AGENT_UPLOAD_BUDGET_BYTES
    fake = -1
    while remaining > 0:
        size = min(remaining, settings.AGENT_UPLOAD_ORG_BUDGET_BYTES)
        await _agent_gate().acquire(fake, fake, size)
        held.append((fake, size))
        remaining -= size
        fake -= 1
    return held


def _free(held: list[tuple[int, int]]) -> None:
    for fake, size in held:
        _agent_gate().release(fake, fake, size)


class _Held:
    """A body that announces its first read, then waits to be released."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(self) -> AsyncIterator[bytes]:
        self.started.set()
        await self.release.wait()
        yield self.body

    def post(self, client):
        return asyncio.create_task(
            client.post(UPLOAD[1], content=self.stream(), headers=_headers(self.body))
        )


def _small_budgets(monkeypatch, *, total: int, org: int, limit: int = 64 * KIB, wait: float = 0.3):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", limit)
    monkeypatch.setattr(settings, "AGENT_UPLOAD_BUDGET_BYTES", total)
    monkeypatch.setattr(settings, "AGENT_UPLOAD_ORG_BUDGET_BYTES", org)
    monkeypatch.setattr(settings, "AGENT_UPLOAD_WAIT_SECONDS", wait)


def test_budgets_below_the_agent_limit_are_rejected_at_startup():
    with pytest.raises(ValueError, match="at least MAX_AGENT_UPLOAD_BYTES"):
        Settings(AGENT_UPLOAD_BUDGET_BYTES=settings.MAX_AGENT_UPLOAD_BYTES - 1)
    with pytest.raises(ValueError, match="at least MAX_AGENT_UPLOAD_BYTES"):
        Settings(AGENT_UPLOAD_ORG_BUDGET_BYTES=settings.MAX_AGENT_UPLOAD_BYTES - 1)
    assert settings.AGENT_UPLOAD_BUDGET_BYTES >= settings.MAX_AGENT_UPLOAD_BYTES
    assert settings.AGENT_UPLOAD_ORG_BUDGET_BYTES >= settings.MAX_AGENT_UPLOAD_BYTES


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


async def test_agent_upload_without_content_length_is_411_unread(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []

    resp = await client.post(
        UPLOAD[1],
        content=_stream([_body(world.a)], yielded),  # an async iterator: sent chunked
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 411, resp.text
    assert resp.json() == {"detail": AGENT_UPLOAD_LENGTH_REQUIRED}
    assert sum(yielded) == 0
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()


async def test_agent_upload_over_limit_is_413(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * KIB)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    resp = await client.post(
        UPLOAD[1],
        content=_body(world.a, 64 * KIB + 1),
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()


@pytest.mark.parametrize("declared", [64 * KIB, KIB], ids=["at-the-limit", "below-the-limit"])
async def test_agent_upload_streaming_past_its_length_is_413(
    world, authz_client, monkeypatch, declared
):
    """A body that outruns its declared length stops at 413 (limit by middleware, length by route)."""
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * KIB)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []
    head = _body(world.a).rstrip()[:-1]  # the JSON minus its closing brace

    resp = await client.post(
        UPLOAD[1],
        content=_stream([head], yielded, filler=b" ", filler_chunk=16 * KIB, total=MIB),
        headers={"content-type": "application/json", "content-length": str(declared)},
    )

    assert resp.status_code == 413, resp.text
    assert resp.json() == {"detail": REQUEST_TOO_LARGE}
    assert sum(yielded) <= 64 * KIB + 16 * KIB
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()


async def test_agent_upload_busy_is_503_unread_at_every_size(world, authz_client, monkeypatch):
    """A full budget refuses a small upload (with a Content-Length) after the wait, body unread."""
    monkeypatch.setattr(settings, "AGENT_UPLOAD_WAIT_SECONDS", 0.2)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    yielded: list[int] = []
    body = _body(world.a)
    held = await _fill_budget()
    try:
        started = time.monotonic()
        resp = await client.post(
            UPLOAD[1], content=_stream([body], yielded), headers=_headers(body)
        )
        assert time.monotonic() - started >= 0.15  # it waited before refusing
        assert resp.status_code == 503, resp.text
        assert resp.json() == {"detail": AGENT_UPLOAD_BUSY}
        assert resp.headers["retry-after"] == "5"
        assert sum(yielded) == 0
        assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    finally:
        _free(held)

    again = await client.post(UPLOAD[1], content=_body(world.a), headers=_headers(_body(world.a)))
    assert again.status_code == ACCEPTED[UPLOAD], again.text
    _assert_slots_free()


async def test_second_upload_for_one_token_is_refused_at_once(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    first = _Held(_body(world.a))
    task = first.post(client)
    await asyncio.wait_for(first.started.wait(), 5)
    yielded: list[int] = []
    body = _body(world.a)

    started = time.monotonic()
    resp = await client.post(UPLOAD[1], content=_stream([body], yielded), headers=_headers(body))

    assert time.monotonic() - started < 2  # no wait: the default is 10 s
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": AGENT_UPLOAD_BUSY}
    assert resp.headers["retry-after"] == "5"
    assert sum(yielded) == 0
    first.release.set()
    assert (await task).status_code == ACCEPTED[UPLOAD]
    _assert_slots_free()


async def test_many_small_uploads_from_different_enrollments_all_succeed(world, authz_client):
    """More than four at once, total well under the budget: none is refused or kept waiting."""
    clients = [await authz_client((await issue_agent(world.a)).raw_token) for _ in range(8)]
    helds = [_Held(_body(world.a)) for _ in clients]
    tasks = [held.post(client) for held, client in zip(helds, clients, strict=True)]
    await asyncio.wait_for(asyncio.gather(*(h.started.wait() for h in helds)), 5)
    assert _agent_uploads_in_flight() > 8  # eight enrollments plus their reserved bytes

    for held in helds:
        held.release.set()
    results = await asyncio.gather(*tasks)

    assert [r.status_code for r in results] == [ACCEPTED[UPLOAD]] * 8, [r.text for r in results]
    _assert_slots_free()


async def test_maximal_uploads_serialize_and_the_second_waits_for_the_first(
    world, authz_client, monkeypatch
):
    _small_budgets(monkeypatch, total=64 * KIB, org=64 * KIB, wait=5.0)
    client_1 = await authz_client((await issue_agent(world.a)).raw_token)
    client_2 = await authz_client((await issue_agent(world.a)).raw_token)
    first = _Held(_body(world.a, 64 * KIB))
    second = _Held(_body(world.a, 64 * KIB))
    task_1 = first.post(client_1)
    await asyncio.wait_for(first.started.wait(), 5)
    task_2 = second.post(client_2)

    await asyncio.sleep(0.4)
    assert not second.started.is_set()  # still waiting; its body has not been read
    assert not task_2.done()

    first.release.set()
    assert (await task_1).status_code == ACCEPTED[UPLOAD]
    await asyncio.wait_for(second.started.wait(), 5)  # woken by the release
    second.release.set()
    assert (await task_2).status_code == ACCEPTED[UPLOAD]
    _assert_slots_free()


async def test_org_share_stops_one_org_from_starving_another(world, authz_client, monkeypatch):
    _small_budgets(monkeypatch, total=128 * KIB, org=64 * KIB, wait=0.3)
    a_1 = await authz_client((await issue_agent(world.a)).raw_token)
    a_2 = await authz_client((await issue_agent(world.a)).raw_token)
    b_1 = await authz_client((await issue_agent(world.b)).raw_token)
    first = _Held(_body(world.a, 64 * KIB))
    task = first.post(a_1)
    await asyncio.wait_for(first.started.wait(), 5)

    # Org A has used its whole share, though half the process budget is free.
    refused = await a_2.post(
        UPLOAD[1], content=_body(world.a, 64 * KIB), headers=_headers(_body(world.a, 64 * KIB))
    )
    other_body = _body(world.b, 64 * KIB)
    other = await b_1.post(UPLOAD[1], content=other_body, headers=_headers(other_body))

    assert refused.status_code == 503, refused.text
    assert refused.json() == {"detail": AGENT_UPLOAD_BUSY}
    assert other.status_code == ACCEPTED[UPLOAD], other.text
    first.release.set()
    assert (await task).status_code == ACCEPTED[UPLOAD]
    _assert_slots_free()


async def test_waiting_for_room_holds_no_pool_connection(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_UPLOAD_WAIT_SECONDS", 5.0)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)  # inside the last-used debounce: verify() commits nothing
    held_budget = await _fill_budget()
    baseline = engine.pool.checkedout()
    held = _Held(_body(world.a))
    task = held.post(client)
    await asyncio.sleep(0.3)

    assert not task.done()
    assert not held.started.is_set()  # still queued, nothing read
    assert engine.pool.checkedout() == baseline

    _free(held_budget)
    await asyncio.wait_for(held.started.wait(), 5)
    held.release.set()
    assert (await task).status_code == ACCEPTED[UPLOAD]
    _assert_slots_free()


async def test_slow_small_upload_does_not_hold_a_pool_connection(world, authz_client):
    """The token check ends its transaction, so a body that trickles in costs no connection."""
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)  # inside the last-used debounce: verify() commits nothing
    baseline = engine.pool.checkedout()
    held = _Held(_body(world.a))
    task = held.post(client)
    await asyncio.wait_for(held.started.wait(), 5)
    await asyncio.sleep(0.2)

    assert engine.pool.checkedout() == baseline

    held.release.set()
    assert (await task).status_code == ACCEPTED[UPLOAD]
    assert engine.pool.checkedout() == baseline


async def test_cancelled_waiter_releases_its_reservation(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_UPLOAD_WAIT_SECONDS", 5.0)
    held = await _fill_budget()
    waiter = asyncio.create_task(_agent_gate().acquire(-100, -100, 1))
    await asyncio.sleep(0.1)
    assert not waiter.done()

    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    _free(held)

    _assert_slots_free()


async def test_agent_upload_without_token_takes_no_slot(world, authz_client):
    client = await authz_client(None)
    before = await snapshot_org(world.a.org_id, world.upload_dir)
    held = await _fill_budget()
    try:
        resp = await client.post(
            UPLOAD[1],
            content=_stream([_body(world.a)], []),
            headers={"content-type": "application/json"},
        )
    finally:
        _free(held)
    assert resp.status_code == 401, resp.text
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()


async def test_stalled_agent_upload_times_out_and_frees_the_slot(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_UPLOAD_READ_TIMEOUT_SECONDS", 0.2)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    await _warm(client, world)
    before = await snapshot_org(world.a.org_id, world.upload_dir)

    async def stalled() -> AsyncIterator[bytes]:
        yield b" " * KIB
        await asyncio.sleep(5)
        yield b" "

    started = time.monotonic()
    resp = await client.post(
        UPLOAD[1],
        content=stalled(),
        headers={"content-type": "application/json", "content-length": str(2 * KIB)},
    )

    assert time.monotonic() - started < 2
    assert resp.status_code == 408, resp.text
    assert resp.json() == {"detail": AGENT_UPLOAD_TIMEOUT}
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()

    body = _body(world.a)
    again = await client.post(UPLOAD[1], content=body, headers=_headers(body))
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
            (b"content-length", b"2048"),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await app(scope, receive, send)

    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert [m["status"] for m in starts] == [400]
    assert await snapshot_org(world.a.org_id, world.upload_dir) == before
    _assert_slots_free()


async def test_agent_upload_at_limit_is_accepted(world, authz_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * KIB)
    client = await authz_client((await issue_agent(world.a)).raw_token)
    body = _body(world.a, 64 * KIB)
    assert len(body) == 64 * KIB

    resp = await client.post(UPLOAD[1], content=body, headers={"content-type": "application/json"})

    assert resp.status_code == ACCEPTED[UPLOAD], resp.text
    _assert_slots_free()


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
    _assert_slots_free()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            json.dumps(
                {"software": [{"vendor": "v" * 200, "product": "p"}] * 20_001},
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
