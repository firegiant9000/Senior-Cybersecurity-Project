"""Public readiness quiz routes (#298): questions and score.

Stateless and unauthenticated. Off unless ENABLE_PUBLIC_READINESS is on, and
404 while the question file is absent. Nothing about a visitor is stored or
logged: no answers, no request body.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import settings
from app.core.limiter import limiter
from app.core.public_readiness import require_public_readiness
from app.services import readiness_quiz

router = APIRouter()

MAX_ANSWERS = 64
_NOT_FOUND = "Not Found"
_BAD_INPUT = "Check your answers and try again."


class QuestionOut(BaseModel):
    id: str
    text: str
    help: str
    options: list[str]


class QuestionsResponse(BaseModel):
    version: str
    questions: list[QuestionOut]


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(max_length=16)
    answers: dict[str, str]

    @field_validator("answers")
    @classmethod
    def _bound_answers(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_ANSWERS:
            raise ValueError("too many answers")
        return value


class GapOut(BaseModel):
    id: str
    title: str
    first_step: str


class WorthFindingOutOut(BaseModel):
    id: str
    question: str
    help: str


class ScoreResponse(BaseModel):
    version: str
    band: str | None
    band_label: str | None
    partial: bool
    answered: int
    total_questions: int
    gaps: list[GapOut]
    worth_finding_out: list[WorthFindingOutOut]
    note: str


def _score_request_schema() -> dict[str, Any]:
    """ScoreRequest JSON schema for OpenAPI (the body is parsed by hand, see below)."""
    schema = ScoreRequest.model_json_schema()
    if "$defs" in schema:  # ScoreRequest has none today; fail loudly if that changes
        raise RuntimeError("ScoreRequest schema has $defs; inline them")
    return schema


def _question_set() -> readiness_quiz.QuestionSet:
    question_set = readiness_quiz.get_question_set()
    if question_set is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return question_set


@router.get(
    "/public/readiness/questions",
    response_model=QuestionsResponse,
    dependencies=[Depends(require_public_readiness)],
)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_READINESS)
async def readiness_questions(request: Request) -> QuestionsResponse:
    """The quiz questions. Weights, sources and gap text are never exposed."""
    question_set = _question_set()
    return QuestionsResponse(
        version=question_set.version,
        questions=[
            QuestionOut(id=q.id, text=q.text, help=q.help, options=list(q.options))
            for q in question_set.questions
        ],
    )


@router.post(
    "/public/readiness/score",
    response_model=ScoreResponse,
    dependencies=[Depends(require_public_readiness)],
    openapi_extra={
        "requestBody": {
            "content": {"application/json": {"schema": _score_request_schema()}},
            "required": True,
        }
    },
)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_READINESS)
async def readiness_score(request: Request) -> ScoreResponse:
    """Score quiz answers. The body is parsed here, after the flag check, so a
    malformed body cannot reveal the route while it is off."""
    try:
        payload = ScoreRequest.model_validate(await request.json())
    except (ValueError, ValidationError, RecursionError):
        raise HTTPException(status_code=422, detail=_BAD_INPUT) from None

    question_set = _question_set()
    try:
        result = readiness_quiz.score_answers(question_set, payload.version, payload.answers)
    except readiness_quiz.AnswerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return ScoreResponse(
        version=result.version,
        band=result.band,
        band_label=result.band_label,
        partial=result.partial,
        answered=result.answered,
        total_questions=result.total_questions,
        gaps=[GapOut(id=g.id, title=g.title, first_step=g.first_step) for g in result.gaps],
        worth_finding_out=[
            WorthFindingOutOut(id=w.id, question=w.question, help=w.help)
            for w in result.worth_finding_out
        ],
        note=result.note,
    )
