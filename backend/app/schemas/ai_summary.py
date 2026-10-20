"""Pydantic schemas for the AI Executive Summary endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.disclaimer import DisclaimerBlock


class RiskItem(BaseModel):
    title: str
    severity: str
    context: str
    # Ids of the input findings this risk is based on. Defaulted so the API
    # response stays backward compatible; the model must send it (CitedRiskItem).
    finding_ids: list[str] = Field(default_factory=list)


# A notable risk as the model returns it: finding_ids is required. (Comments,
# not docstrings: pydantic would send a docstring to Gemini as a description.)
class CitedRiskItem(RiskItem):
    finding_ids: list[str]


class GapItem(BaseModel):
    gap_type: str
    impact: str


class StepItem(BaseModel):
    priority: int
    action: str
    rationale: str


# The model's output, and Gemini's response_schema.
class StructuredSummary(BaseModel):
    narrative: str
    posture_statement: str
    notable_risks: list[CitedRiskItem]
    data_gaps: list[GapItem]
    next_steps: list[StepItem]


class AISummaryResponse(BaseModel):
    narrative: str
    ai_generated: bool
    model_used: str | None
    findings_count: int
    risk_score: float
    risk_label: str
    generated_at: str
    cached: bool
    disclaimer: str
    disclaimer_block: DisclaimerBlock | None = None
    output_format: str = "prose"
    posture_statement: str | None = None
    notable_risks: list[RiskItem] | None = None
    data_gaps: list[GapItem] | None = None
    next_steps: list[StepItem] | None = None
