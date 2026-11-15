"""Tests for the closed step set for funnel events (#296)."""

import pytest

from app.services import readiness_funnel, readiness_quiz
from tests.test_readiness_quiz import load_fixture_set

FIXED = [
    "domain_check_started",
    "domain_check_completed",
    "quiz_started",
    "quiz_completed",
    "signup_clicked",
]


@pytest.fixture
def fixture_questions(monkeypatch):
    monkeypatch.setattr(readiness_quiz, "get_question_set", load_fixture_set)


@pytest.mark.parametrize("step", FIXED)
def test_fixed_steps_are_known(fixture_questions, step):
    assert readiness_funnel.is_known_event("v1", step) is True


def test_question_step_known_for_current_ids(fixture_questions):
    assert readiness_funnel.is_known_event("v1", "question_answered:fixture_a") is True


@pytest.mark.parametrize(
    "step",
    [
        "question_answered:",
        "question_answered:nope",
        "question_answered:FIXTURE_A",
        "question_answered:fixture_a ",
        "Quiz_started",
        "",
        "quiz_started:x",
        "x" * 200,
    ],
)
def test_unknown_steps_rejected(fixture_questions, step):
    assert readiness_funnel.is_known_event("v1", step) is False


@pytest.mark.parametrize("version", ["v2", "V1", ""])
def test_unknown_version_rejected(fixture_questions, version):
    assert readiness_funnel.is_known_event(version, "quiz_started") is False


def test_no_question_file_rejects_question_steps_only(monkeypatch):
    monkeypatch.setattr(readiness_quiz, "get_question_set", lambda: None)
    assert readiness_funnel.is_known_event("v1", "question_answered:fixture_a") is False
    assert readiness_funnel.is_known_event("v1", "quiz_started") is True


def test_loader_error_propagates(monkeypatch):
    def failing_loader():
        raise ValueError("mismatch")

    monkeypatch.setattr(readiness_quiz, "get_question_set", failing_loader)
    with pytest.raises(ValueError, match="mismatch"):
        readiness_funnel.is_known_event("v1", "question_answered:fixture_a")
    # Fixed steps never reach the loader, so the raising patch is not hit.
    assert readiness_funnel.is_known_event("v1", "quiz_started") is True
