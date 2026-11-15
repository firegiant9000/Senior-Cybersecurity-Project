"""Tests for the public readiness quiz question-set schema and loader (#298)."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services import readiness_quiz
from app.services.readiness_quiz import (
    BAND_LABELS,
    LOSS_HALVES,
    MIDDLE_BAND_MIN_PERCENT,
    QUESTIONS_PATH,
    RESULT_NOTE,
    TOP_BAND_MIN_PERCENT,
    AnswerError,
    QuestionSet,
    load_question_set,
    score_answers,
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


# --- scoring -----------------------------------------------------------------
# Fixture: A (w3, has partly + n/a), B (w2, yes/no/not_sure), C (w1, has partly),
# D (w3, has n/a).


def _answers(a="yes", b="yes", c="yes", d="yes") -> dict[str, str]:
    return {"fixture_a": a, "fixture_b": b, "fixture_c": c, "fixture_d": d}


def _score(answers):
    return score_answers(load_fixture_set(), "v1", answers)


def _flat_set(weights: list[int]) -> QuestionSet:
    """Tiny valid set: one yes/no/not_sure question per weight (ids q0, q1, ...)."""
    return QuestionSet.model_validate(
        {
            "version": "v1",
            "questions": [
                {
                    "id": f"q{i}",
                    "text": "T?",
                    "help": "H.",
                    "options": ["yes", "no", "not_sure"],
                    "weight": w,
                    "weight_reason": "R.",
                    "gap_title": f"Gap {i}",
                    "gap_first_step": "Step.",
                    "sources": ["S"],
                }
                for i, w in enumerate(weights)
            ],
        }
    )


def test_all_yes_is_top_band_with_no_gaps():
    result = _score(_answers())
    assert result.band == "well_prepared"
    assert result.band_label == BAND_LABELS["well_prepared"]
    assert result.gaps == []
    assert result.worth_finding_out == []
    assert result.partial is False
    assert result.note == RESULT_NOTE
    assert result.version == "v1"


def test_all_no_is_bottom_band_and_every_question_is_a_gap():
    result = _score(_answers("no", "no", "no", "no"))
    assert result.band == "significant_gaps"
    assert result.band_label == "Significant gaps"
    # Lost half-units: A 6, D 6 (tie, weight equal -> file order), B 4, C 2.
    assert [g.id for g in result.gaps] == ["fixture_a", "fixture_d", "fixture_b", "fixture_c"]
    assert result.gaps[0].title == "Fixture gap A"
    assert result.gaps[0].first_step == "Fixture first step A."


def test_all_not_sure_is_bottom_band_with_no_gaps_and_all_worth_finding_out():
    result = _score(_answers("not_sure", "not_sure", "not_sure", "not_sure"))
    assert result.band == "significant_gaps"
    assert result.gaps == []
    assert [w.id for w in result.worth_finding_out] == [
        "fixture_a",
        "fixture_b",
        "fixture_c",
        "fixture_d",
    ]
    assert result.worth_finding_out[0].question == "Fixture question A?"
    assert result.worth_finding_out[0].help == "Fixture help A."


def test_partial_answers_are_marked_partial():
    result = _score({"fixture_a": "yes", "fixture_b": "no"})
    assert result.partial is True
    assert result.answered == 2
    assert result.total_questions == 4


def test_gap_order_heaviest_first():
    # D no (w3: 6 half-units), A partly (w3: 3), C no (w1: 2).
    result = _score({"fixture_c": "no", "fixture_a": "partly", "fixture_d": "no"})
    assert [g.id for g in result.gaps] == ["fixture_d", "fixture_a", "fixture_c"]


def test_not_applicable_is_left_out_of_the_total():
    # Only B (w2, yes) and C (w1, no) count: kept2 = 6 - 2 = 4 of 6 -> 66% -> some_gaps.
    # If n/a were counted as kept, 16 of 18 would be 88% -> well_prepared.
    result = _score(
        {
            "fixture_a": "not_applicable",
            "fixture_b": "yes",
            "fixture_c": "no",
            "fixture_d": "not_applicable",
        }
    )
    assert result.band == "some_gaps"
    assert [g.id for g in result.gaps] == ["fixture_c"]


def test_band_boundaries_are_inclusive():
    # 80%: five weight-1 questions, one "no". total2 = 2*5 = 10, lost = 1*2 = 2,
    # kept2 = 8 -> 8*100 == 80*10 exactly.
    top = score_answers(
        _flat_set([1] * 5), "v1", {"q0": "no", "q1": "yes", "q2": "yes", "q3": "yes", "q4": "yes"}
    )
    assert top.band == "well_prepared"
    # 50%: two weight-1 questions, one "no". total2 = 4, lost = 2, kept2 = 2 -> 200 == 50*4.
    middle = score_answers(_flat_set([1, 1]), "v1", {"q0": "no", "q1": "yes"})
    assert middle.band == "some_gaps"
    # Just under 50%: three weight-1 questions, two "no". kept2 = 2 of 6 -> 33%.
    below = score_answers(_flat_set([1] * 3), "v1", {"q0": "no", "q1": "no", "q2": "yes"})
    assert below.band == "significant_gaps"


@pytest.mark.parametrize(
    "answers",
    [{}, {"fixture_a": "not_applicable", "fixture_d": "not_applicable"}],
    ids=["empty", "all_not_applicable"],
)
def test_nothing_counted_gives_no_band(answers):
    result = _score(answers)
    assert result.band is None
    assert result.band_label is None
    assert result.gaps == []
    assert result.note == RESULT_NOTE


@pytest.mark.parametrize(
    ("version", "answers", "message"),
    [
        ("v9", {"fixture_a": "yes"}, "Unknown question set version."),
        ("v1", {"zz_secret_id": "yes"}, "Unknown question."),
        ("v1", {"fixture_b": "partly"}, "Answer not allowed for this question."),
        ("v1", {"fixture_a": "zz_secret_value"}, "Answer not allowed for this question."),
    ],
    ids=["wrong_version", "unknown_id", "option_not_offered", "unknown_option"],
)
def test_invalid_answers_raise(version, answers, message):
    with pytest.raises(AnswerError) as exc_info:
        score_answers(load_fixture_set(), version, answers)
    assert str(exc_info.value) == message
    for offending in ("v9", "zz_secret_id", "zz_secret_value", "partly"):
        assert offending not in str(exc_info.value)


def test_scoring_constants():
    assert LOSS_HALVES == {"yes": 0, "partly": 1, "no": 2, "not_sure": 2}
    assert TOP_BAND_MIN_PERCENT == 80
    assert MIDDLE_BAND_MIN_PERCENT == 50
    assert BAND_LABELS == {
        "well_prepared": "Well prepared",
        "some_gaps": "Some gaps to close",
        "significant_gaps": "Significant gaps",
    }
    assert (
        RESULT_NOTE
        == "These are gaps that insurers commonly ask about. This is not insurance advice."
    )
