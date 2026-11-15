"""Public readiness quiz (#298): question-set schema and loader.

The question content lives in a data file delivered separately (#294). With the
file absent, ``get_question_set()`` returns None and the quiz routes answer 404.
Nothing about a visitor is stored or logged.
"""

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


@cache
def get_question_set() -> QuestionSet | None:
    """Cached question set from QUESTIONS_PATH (tests: ``get_question_set.cache_clear()``)."""
    question_set = load_question_set(QUESTIONS_PATH)
    if question_set is not None and question_set.version != QUESTIONS_VERSION:
        raise ValueError("question file version does not match QUESTIONS_PATH")
    return question_set
