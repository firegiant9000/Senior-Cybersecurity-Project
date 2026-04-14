"""Pydantic schemas for the Assessment Readiness endpoint."""

from pydantic import BaseModel


class ReadinessItem(BaseModel):
    key: str
    label: str
    complete: bool
    required: bool
    detail: str


class AssessmentReadinessResponse(BaseModel):
    is_ready: bool
    readiness_pct: float
    tier: str
    items: list[ReadinessItem]
    next_steps: list[str]
