"""Pydantic schemas for the assessment validation endpoint."""

from pydantic import BaseModel


class ValidationIssueResponse(BaseModel):
    category: str       # "missing_field" | "duplicate" | "invalid_format" | "conflict" | "quality"
    severity: str       # "error" | "warning" | "info"
    field: str
    message: str
    suggestion: str | None = None


class AssessmentValidationResponse(BaseModel):
    issues: list[ValidationIssueResponse]
    score: float
    passed: bool
    issue_counts: dict[str, int]
