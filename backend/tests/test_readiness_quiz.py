"""Tests for the public readiness quiz question-set schema and loader (#298)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services import readiness_quiz
from app.services.readiness_quiz import (
    QUESTIONS_PATH,
    QuestionSet,
    load_question_set,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "readiness" / "questions_fixture.json"


def load_fixture_set() -> QuestionSet:
    """Load the placeholder question set (shared by the scoring and route tests)."""
    question_set = load_question_set(FIXTURE_PATH)
    assert question_set is not None
    return question_set


def fixture_dict() -> dict:
    return copy.deepcopy(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _dup_id(d: dict) -> None:
    d["questions"][1]["id"] = d["questions"][0]["id"]


def _no_not_sure(d: dict) -> None:
    d["questions"][1]["options"] = ["yes", "no"]


def _weight(value: int):
    def mutate(d: dict) -> None:
        d["questions"][0]["weight"] = value

    return mutate


def _empty_gap_title(d: dict) -> None:
    d["questions"][0]["gap_title"] = ""


def _blank_gap_title(d: dict) -> None:
    d["questions"][0]["gap_title"] = "   "


def _empty_source(d: dict) -> None:
    d["questions"][0]["sources"] = [""]


def _missing_first_step(d: dict) -> None:
    del d["questions"][0]["gap_first_step"]


def _unknown_option(d: dict) -> None:
    d["questions"][1]["options"] = ["yes", "no", "not_sure", "maybe"]


def _extra_field(d: dict) -> None:
    d["questions"][0]["surprise"] = "x"


def _dup_option(d: dict) -> None:
    d["questions"][1]["options"] = ["yes", "no", "not_sure", "yes"]


def test_fixture_loads():
    question_set = load_fixture_set()
    assert question_set.version == "v1"
    assert len(question_set.questions) == 4


def test_missing_file_returns_none(tmp_path):
    assert load_question_set(tmp_path / "absent.json") is None


@pytest.mark.parametrize(
    "mutate",
    [
        _dup_id,
        _no_not_sure,
        _weight(0),
        _weight(4),
        _empty_gap_title,
        _missing_first_step,
        _unknown_option,
        _extra_field,
        _dup_option,
        _blank_gap_title,
        _empty_source,
    ],
    ids=[
        "duplicate_id",
        "missing_not_sure",
        "weight_0",
        "weight_4",
        "empty_gap_title",
        "missing_gap_first_step",
        "unknown_option",
        "extra_field",
        "duplicate_option",
        "blank_gap_title",
        "empty_source",
    ],
)
def test_invalid_question_set_rejected(mutate):
    data = fixture_dict()
    mutate(data)
    with pytest.raises(ValidationError):
        QuestionSet.model_validate(data)


def test_get_question_set_is_cached_and_clearable(monkeypatch):
    monkeypatch.setattr(readiness_quiz, "QUESTIONS_PATH", FIXTURE_PATH)
    readiness_quiz.get_question_set.cache_clear()
    try:
        first = readiness_quiz.get_question_set()
        assert first is not None
        assert readiness_quiz.get_question_set() is first
    finally:
        readiness_quiz.get_question_set.cache_clear()


def test_loaded_set_is_immutable_tuples():
    question_set = load_fixture_set()
    assert isinstance(question_set.questions, tuple)
    assert isinstance(question_set.questions[0].options, tuple)
    assert isinstance(question_set.questions[0].sources, tuple)


def test_get_question_set_rejects_version_mismatch(monkeypatch, tmp_path):
    data = fixture_dict()
    data["version"] = "v2"
    path = tmp_path / "questions_v2.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(readiness_quiz, "QUESTIONS_PATH", path)
    readiness_quiz.get_question_set.cache_clear()
    try:
        with pytest.raises(ValueError, match="question file version does not match QUESTIONS_PATH"):
            readiness_quiz.get_question_set()
    finally:
        readiness_quiz.get_question_set.cache_clear()


def test_real_question_file_is_valid():
    if not QUESTIONS_PATH.exists():
        pytest.skip("questions_v1.json not delivered yet (#294)")
    question_set = load_question_set(QUESTIONS_PATH)
    assert question_set is not None
    ids = [q.id for q in question_set.questions]
    assert len(ids) == len(set(ids)), f"duplicate question ids in {QUESTIONS_PATH.name}"
    for q in question_set.questions:
        assert "not_sure" in q.options, f"{q.id}: must offer not_sure"
        assert 1 <= q.weight <= 3, f"{q.id}: weight {q.weight} outside 1..3"
        assert q.gap_title.strip(), f"{q.id}: gap_title is empty"
        assert q.gap_first_step.strip(), f"{q.id}: gap_first_step is empty"
