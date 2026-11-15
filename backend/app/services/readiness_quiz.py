"""Public readiness quiz (#298): question-set schema and loader.

The question content lives in a data file delivered separately (#294). With the
file absent, ``get_question_set()`` returns None and the quiz routes answer 404.
Nothing about a visitor is stored or logged.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

OptionId = Literal["yes", "partly", "no", "not_sure", "not_applicable"]
REQUIRED_OPTIONS = frozenset({"yes", "no", "not_sure"})
IntakeField = Literal[
    "mfa_enabled",
    "endpoint_protection",
    "backup_strategy",
    "incident_response_plan",
]
QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "readiness" / "questions_v1.json"
MAX_QUESTIONS = 30

QUESTIONS_VERSION = "v1"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    text: NonEmptyStr
    help: NonEmptyStr
    options: tuple[OptionId, ...]
    weight: Annotated[int, Field(ge=1, le=3)]
    weight_reason: NonEmptyStr
    gap_title: NonEmptyStr
    gap_first_step: NonEmptyStr
    sources: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    intake_field: IntakeField | None = None

    @field_validator("options")
    @classmethod
    def _check_options(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("options must be unique")
        missing = REQUIRED_OPTIONS - set(value)
        if missing:
            raise ValueError(f"options must include {sorted(REQUIRED_OPTIONS)}")
        return value


class QuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Annotated[str, StringConstraints(pattern=r"^v[0-9]{1,3}$")]
    questions: Annotated[tuple[Question, ...], Field(min_length=1, max_length=MAX_QUESTIONS)]

    @model_validator(mode="after")
    def _check_unique_ids(self) -> "QuestionSet":
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("question ids must be unique")
        return self


def load_question_set(path: Path) -> QuestionSet | None:
    """Load and validate a question file. None if absent; ValidationError if invalid."""
    if not path.exists():
        return None
    return QuestionSet.model_validate_json(path.read_text(encoding="utf-8"))


LOSS_HALVES: dict[OptionId, int] = {"yes": 0, "partly": 1, "no": 2, "not_sure": 2}
"""Half-units of weight lost per answer. ``not_applicable`` is excluded from scoring."""
TOP_BAND_MIN_PERCENT = 80
MIDDLE_BAND_MIN_PERCENT = 50
Band = Literal["well_prepared", "some_gaps", "significant_gaps"]
BAND_LABELS: dict[Band, str] = {
    "well_prepared": "Well prepared",
    "some_gaps": "Some gaps to close",
    "significant_gaps": "Significant gaps",
}
RESULT_NOTE = "These are gaps that insurers commonly ask about. This is not insurance advice."


class AnswerError(ValueError):
    """Invalid answers. The message is app-authored and never contains caller input."""


@dataclass(frozen=True)
class Gap:
    id: str
    title: str
    first_step: str


@dataclass(frozen=True)
class WorthFindingOut:
    id: str
    question: str
    help: str


@dataclass(frozen=True)
class ReadinessResult:
    version: str
    band: Band | None
    band_label: str | None
    partial: bool
    answered: int
    total_questions: int
    gaps: list[Gap]
    worth_finding_out: list[WorthFindingOut]
    note: str


def _band_for(kept2: int, total2: int) -> Band | None:
    """Integer-only band decision (no floats); None when nothing was counted."""
    if total2 == 0:
        return None
    if kept2 * 100 >= TOP_BAND_MIN_PERCENT * total2:
        return "well_prepared"
    if kept2 * 100 >= MIDDLE_BAND_MIN_PERCENT * total2:
        return "some_gaps"
    return "significant_gaps"


def _validate_answers(qs: QuestionSet, version: str, answers: Mapping[str, str]) -> None:
    if version != qs.version:
        raise AnswerError("Unknown question set version.")
    by_id = {q.id: q for q in qs.questions}
    for question_id, option in answers.items():
        question = by_id.get(question_id)
        if question is None:
            raise AnswerError("Unknown question.")
        if option not in question.options:
            raise AnswerError("Answer not allowed for this question.")


def score_answers(qs: QuestionSet, version: str, answers: Mapping[str, str]) -> ReadinessResult:
    """Pure scoring: integer half-unit arithmetic, no I/O, no logging."""
    _validate_answers(qs, version, answers)

    total2 = 0
    lost2 = 0
    ranked_gaps: list[tuple[int, int, int, Question]] = []
    worth: list[WorthFindingOut] = []
    for index, q in enumerate(qs.questions):
        answer = answers.get(q.id)
        if answer is None or answer == "not_applicable":
            continue
        loss = q.weight * LOSS_HALVES[answer]  # type: ignore[index]
        total2 += 2 * q.weight
        lost2 += loss
        if answer in ("no", "partly"):
            ranked_gaps.append((-loss, -q.weight, index, q))
        elif answer == "not_sure":
            worth.append(WorthFindingOut(id=q.id, question=q.text, help=q.help))
    ranked_gaps.sort(key=lambda item: item[:3])

    band = _band_for(total2 - lost2, total2)

    return ReadinessResult(
        version=qs.version,
        band=band,
        band_label=BAND_LABELS[band] if band else None,
        partial=len(answers) < len(qs.questions),
        answered=len(answers),
        total_questions=len(qs.questions),
        gaps=[
            Gap(id=q.id, title=q.gap_title, first_step=q.gap_first_step) for *_, q in ranked_gaps
        ],
        worth_finding_out=worth,
        note=RESULT_NOTE,
    )


@cache
def get_question_set() -> QuestionSet | None:
    """Cached question set from QUESTIONS_PATH (tests: ``get_question_set.cache_clear()``)."""
    question_set = load_question_set(QUESTIONS_PATH)
    if question_set is not None and question_set.version != QUESTIONS_VERSION:
        raise ValueError("question file version does not match QUESTIONS_PATH")
    return question_set
