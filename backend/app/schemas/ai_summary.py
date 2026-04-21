"""Pydantic schemas for the AI Executive Summary endpoint."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.disclaimer import DisclaimerBlock


class RiskItem(BaseModel):
    title: str
    severity: str
    context: str


class GapItem(BaseModel):
    gap_type: str
    impact: str


class StepItem(BaseModel):
    priority: int
    action: str
    rationale: str


class StructuredSummary(BaseModel):
    narrative: str
    posture_statement: str
    notable_risks: list[RiskItem]
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
