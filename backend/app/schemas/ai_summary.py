"""Pydantic schemas for the AI Executive Summary endpoint."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.disclaimer import DisclaimerBlock


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
