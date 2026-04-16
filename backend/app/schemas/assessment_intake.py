"""Pydantic schemas for the graduated Assessment Intake tier system."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class AssessmentTier(StrEnum):
    INCOMPLETE = "incomplete"
    BASIC = "basic"
    ENHANCED = "enhanced"
    COMPREHENSIVE = "comprehensive"


class TierRequirement(BaseModel):
    key: str
    label: str
    met: bool
    detail: str


class TierDefinition(BaseModel):
    tier: AssessmentTier
    label: str
    description: str
    requirements: list[TierRequirement]
    all_met: bool
    unlocks: list[str]


class AssessmentIntakeResponse(BaseModel):
    current_tier: AssessmentTier
    tiers: list[TierDefinition]
    next_tier: AssessmentTier | None
    next_tier_progress: float
    fields_to_advance: list[str]
