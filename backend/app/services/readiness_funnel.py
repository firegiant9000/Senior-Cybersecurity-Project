"""Closed step set for the anonymous readiness funnel counters (#296).

Only the names below are counted. A question step is known only when its id is in
the current question set, so unknown or stale names are rejected. Nothing about a
visitor is stored or logged.
"""

from app.services import readiness_quiz

FIXED_STEPS: frozenset[str] = frozenset(
    {
        "domain_check_started",
        "domain_check_completed",
        "quiz_started",
        "quiz_completed",
        "signup_clicked",
    }
)
QUESTION_STEP_PREFIX = "question_answered:"


def is_known_event(version: str, step: str) -> bool:
    """Return True when ``step`` is a countable step for question-set ``version``.

    Exceptions from ``get_question_set()`` are not caught.
    """
    if version != readiness_quiz.QUESTIONS_VERSION:
        return False
    if step in FIXED_STEPS:
        return True
    if step.startswith(QUESTION_STEP_PREFIX):
        question_set = readiness_quiz.get_question_set()
        if question_set is None:
            return False
        question_id = step[len(QUESTION_STEP_PREFIX) :]
        return any(question.id == question_id for question in question_set.questions)
    return False
