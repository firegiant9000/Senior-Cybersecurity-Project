"""Public readiness funnel event route (#296): flag, validation, counting, no logging, limit."""

import json
import logging
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import AsyncSessionLocal
from app.db.readiness_funnel_count import ReadinessFunnelCount
from app.repositories.readiness_funnel import FunnelCountRow, SqlReadinessFunnelRepository
from app.services import readiness_quiz
from tests.test_readiness_quiz import load_fixture_set

EVENTS_URL = "/api/v1/public/readiness/events"
JSON_HEADERS = {"Content-Type": "application/json"}
STARTED = {"version": "v1", "step": "quiz_started"}


async def _wipe() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ReadinessFunnelCount))
        await session.commit()


async def _rows() -> list[FunnelCountRow]:
    today = datetime.now(UTC).date()
    async with AsyncSessionLocal() as session:
        return await SqlReadinessFunnelRepository(session).counts_between(today, today)


@pytest_asyncio.fixture
async def events_client(client: AsyncClient, monkeypatch):
    """Flag on, loader pointed at the fixture, clean limiter and table."""
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", True)
    monkeypatch.setattr(readiness_quiz, "get_question_set", load_fixture_set)
    limiter.reset()
    await _wipe()
    try:
        yield client
    finally:
        limiter.reset()
        await _wipe()


@pytest.mark.asyncio
async def test_events_flag_off_returns_404(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", False)
    monkeypatch.setattr(readiness_quiz, "get_question_set", load_fixture_set)
    limiter.reset()
    await _wipe()
    try:
        for kwargs in (
            {"json": STARTED},
            {"content": b"{bad", "headers": JSON_HEADERS},
            {"json": {"version": "v9"}},
        ):
            resp = await client.post(EVENTS_URL, **kwargs)
            assert resp.status_code == 404
            assert resp.json() == {"detail": "Not Found"}
        assert await _rows() == []
    finally:
        limiter.reset()
        await _wipe()


@pytest.mark.asyncio
async def test_event_increment_creates_then_updates(events_client: AsyncClient):
    resp = await events_client.post(EVENTS_URL, json=STARTED)
    assert resp.status_code == 204
    assert resp.content == b""
    rows = await _rows()
    assert len(rows) == 1
    assert (rows[0].version, rows[0].step, rows[0].count) == ("v1", "quiz_started", 1)

    resp = await events_client.post(EVENTS_URL, json=STARTED)
    assert resp.status_code == 204
    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].count == 2


@pytest.mark.asyncio
async def test_many_requests_same_step_leave_one_row(events_client: AsyncClient):
    body = {"version": "v1", "step": "question_answered:fixture_b"}
    for _ in range(25):
        assert (await events_client.post(EVENTS_URL, json=body)).status_code == 204
    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].count == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"{bad", id="malformed-json"),
        pytest.param(b"[]", id="empty-list"),
        pytest.param(json.dumps({"version": "v1"}).encode(), id="missing-step"),
        pytest.param(
            json.dumps({"version": "v1", "step": "quiz_started", "extra": 1}).encode(),
            id="extra-field",
        ),
        pytest.param(
            json.dumps({"version": "v2", "step": "quiz_started"}).encode(), id="unknown-version"
        ),
        pytest.param(json.dumps({"version": "v1", "step": "nope"}).encode(), id="unknown-step"),
        pytest.param(
            json.dumps({"version": "v1", "step": "question_answered:nope"}).encode(),
            id="unknown-question",
        ),
        pytest.param(json.dumps({"version": "v1", "step": "x" * 200}).encode(), id="step-too-long"),
        pytest.param(b"[" * 2000 + b"]" * 2000, id="deeply-nested"),
    ],
)
async def test_invalid_event_is_422(events_client: AsyncClient, content: bytes):
    resp = await events_client.post(EVENTS_URL, content=content, headers=JSON_HEADERS)
    assert resp.status_code == 422
    assert resp.json() == {"detail": "Unknown event."}
    assert "nope" not in resp.text
    assert await _rows() == []


@pytest.mark.asyncio
async def test_question_steps_rejected_without_question_file(
    events_client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(readiness_quiz, "get_question_set", lambda: None)
    resp = await events_client.post(
        EVENTS_URL, json={"version": "v1", "step": "question_answered:fixture_a"}
    )
    assert resp.status_code == 422
    resp = await events_client.post(EVENTS_URL, json=STARTED)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_event_body_not_logged(events_client: AsyncClient, caplog):
    caplog.set_level(logging.DEBUG)
    resp = await events_client.post(EVENTS_URL, json=STARTED)
    assert resp.status_code == 204
    for record in caplog.records:
        assert "quiz_started" not in record.getMessage()


@pytest.mark.asyncio
async def test_events_client_disconnect_is_400(events_client: AsyncClient):
    from app.main import app

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": EVENTS_URL,
        "raw_path": EVENTS_URL.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", b"100"),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    events = [
        {"type": "http.request", "body": b'{"version": "v1", "st', "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent: list[dict] = []

    async def receive():
        return events.pop(0) if events else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)

    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert starts, "no response was sent"
    assert starts[0]["status"] == 400


@pytest.mark.asyncio
async def test_events_rate_limit_returns_429(events_client: AsyncClient):
    for _ in range(60):
        assert (await events_client.post(EVENTS_URL, json=STARTED)).status_code == 204
    assert (await events_client.post(EVENTS_URL, json=STARTED)).status_code == 429
