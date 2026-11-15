"""Public readiness quiz routes (#298): flag, 404s, validation, no logging, rate limit."""

import json
import logging

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.routes.v1 import public_readiness
from app.core.config import settings
from app.core.limiter import limiter
from app.main import app
from app.services import readiness_quiz
from app.services.readiness_quiz import RESULT_NOTE, score_answers
from tests.test_readiness_quiz import load_fixture_set

QUESTIONS_URL = "/api/v1/public/readiness/questions"
SCORE_URL = "/api/v1/public/readiness/score"
JSON_HEADERS = {"Content-Type": "application/json"}
GOOD_ANSWERS = {"fixture_a": "yes", "fixture_b": "no", "fixture_c": "not_sure"}
GOOD_BODY = {"version": "v1", "answers": GOOD_ANSWERS}


@pytest_asyncio.fixture
async def quiz_client(client: AsyncClient, monkeypatch):
    """Flag on, loader pointed at the fixture, clean limiter."""
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", True)
    monkeypatch.setattr(readiness_quiz, "get_question_set", load_fixture_set)
    limiter.reset()
    try:
        yield client
    finally:
        limiter.reset()


@pytest.mark.asyncio
async def test_flag_off_returns_404(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", False)
    monkeypatch.setattr(readiness_quiz, "get_question_set", load_fixture_set)
    limiter.reset()
    try:
        resp = await client.get(QUESTIONS_URL)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}
        resp = await client.post(SCORE_URL, json=GOOD_BODY)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}
        # A malformed body must not reveal the route while the flag is off.
        resp = await client.post(SCORE_URL, content=b"{bad", headers=JSON_HEADERS)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}
    finally:
        limiter.reset()


@pytest.mark.asyncio
async def test_no_question_file_returns_404(quiz_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(readiness_quiz, "get_question_set", lambda: None)
    resp = await quiz_client.get(QUESTIONS_URL)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}
    resp = await quiz_client.post(SCORE_URL, json=GOOD_BODY)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


@pytest.mark.asyncio
async def test_questions_response_has_no_weights(quiz_client: AsyncClient):
    resp = await quiz_client.get(QUESTIONS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"version", "questions"}
    assert body["version"] == "v1"
    assert len(body["questions"]) == 4
    for question in body["questions"]:
        assert set(question) == {"id", "text", "help", "options"}
    for hidden in ("weight", "gap_title", "sources", "intake_field"):
        assert hidden not in resp.text


@pytest.mark.asyncio
async def test_score_happy_path(quiz_client: AsyncClient):
    resp = await quiz_client.post(SCORE_URL, json=GOOD_BODY)
    assert resp.status_code == 200
    expected = score_answers(load_fixture_set(), "v1", GOOD_ANSWERS)
    body = resp.json()
    assert body["version"] == expected.version
    assert body["band"] == expected.band
    assert body["band_label"] == expected.band_label
    assert body["partial"] == expected.partial
    assert body["answered"] == expected.answered
    assert body["total_questions"] == expected.total_questions
    assert body["gaps"] == [
        {"id": g.id, "title": g.title, "first_step": g.first_step} for g in expected.gaps
    ]
    assert body["worth_finding_out"] == [
        {"id": w.id, "question": w.question, "help": w.help} for w in expected.worth_finding_out
    ]
    assert body["note"] == RESULT_NOTE


@pytest.mark.asyncio
async def test_score_all_not_applicable_allows_null_band(quiz_client: AsyncClient):
    answers = {"fixture_a": "not_applicable", "fixture_d": "not_applicable"}
    resp = await quiz_client.post(SCORE_URL, json={"version": "v1", "answers": answers})
    assert resp.status_code == 200
    assert resp.json()["band"] is None


VICTIM = "victim-answer-xyz"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content"),
    [
        pytest.param(
            json.dumps({"version": "v9", "answers": GOOD_ANSWERS}).encode(), id="unknown-version"
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": {VICTIM: "yes"}}).encode(), id="unknown-id"
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": {"fixture_b": "partly"}}).encode(),
            id="disallowed-option",
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": {"fixture_a": "maybe"}}).encode(),
            id="option-maybe",
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": GOOD_ANSWERS, "extra": VICTIM}).encode(),
            id="extra-field",
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": {f"q{i}": VICTIM for i in range(65)}}).encode(),
            id="65-answers",
        ),
        pytest.param(
            json.dumps({"version": "v1", "answers": VICTIM}).encode(), id="answers-not-object"
        ),
        pytest.param(b"{bad", id="malformed-json"),
        pytest.param(b"[" * 100000, id="deeply-nested"),
        pytest.param(b"[]", id="empty-list"),
        pytest.param(json.dumps({"version": "v1", "answers": []}).encode(), id="answers-list"),
        pytest.param(
            json.dumps({"version": "v" * 100, "answers": GOOD_ANSWERS}).encode(),
            id="version-too-long",
        ),
    ],
)
async def test_invalid_score_input_is_422(quiz_client: AsyncClient, content: bytes):
    resp = await quiz_client.post(SCORE_URL, content=content, headers=JSON_HEADERS)
    assert resp.status_code == 422
    assert VICTIM not in resp.text
    assert "{bad" not in resp.text
    assert isinstance(resp.json()["detail"], str)


@pytest.mark.asyncio
async def test_answer_cap_is_enforced(quiz_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(public_readiness, "MAX_ANSWERS", 1)
    resp = await quiz_client.post(SCORE_URL, json=GOOD_BODY)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Check your answers and try again."


@pytest.mark.asyncio
async def test_version_mismatch_is_a_server_error(monkeypatch):
    def _boom():
        raise ValueError("question file version does not match QUESTIONS_PATH")

    monkeypatch.setattr(settings, "ENABLE_PUBLIC_READINESS", True)
    monkeypatch.setattr(readiness_quiz, "get_question_set", _boom)
    limiter.reset()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as c:
            resp = await c.post(SCORE_URL, json=GOOD_BODY)
    finally:
        limiter.reset()
    assert resp.status_code == 500
    assert "QUESTIONS_PATH" not in resp.text
    assert "does not match" not in resp.text


@pytest.mark.asyncio
async def test_result_wording_makes_no_decision(quiz_client: AsyncClient):
    resp = await quiz_client.post(SCORE_URL, json=GOOD_BODY)
    text = resp.text.lower()
    for word in ("approv", "eligib", "premium", "price", "denied", "guarantee"):
        assert word not in text


@pytest.mark.asyncio
async def test_answers_are_not_logged(quiz_client: AsyncClient, caplog):
    caplog.set_level(logging.DEBUG)
    raw = json.dumps(GOOD_BODY)
    resp = await quiz_client.post(SCORE_URL, content=raw, headers=JSON_HEADERS)
    assert resp.status_code == 200
    for record in caplog.records:
        message = record.getMessage()
        assert raw not in message
        assert str(GOOD_ANSWERS) not in message
        for question_id, answer in GOOD_ANSWERS.items():
            assert not (question_id in message and answer in message)


@pytest.mark.asyncio
async def test_client_disconnect_mid_body_is_not_a_500(quiz_client: AsyncClient):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": SCORE_URL,
        "raw_path": SCORE_URL.encode(),
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
        {"type": "http.request", "body": b'{"version": "v1", "ans', "more_body": True},
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
    assert starts[0]["status"] != 500


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["questions", "score"])
async def test_rate_limit_returns_429(quiz_client: AsyncClient, route: str):
    async def call():
        if route == "questions":
            return await quiz_client.get(QUESTIONS_URL)
        return await quiz_client.post(SCORE_URL, json=GOOD_BODY)

    for _ in range(30):
        assert (await call()).status_code == 200
    assert (await call()).status_code == 429
