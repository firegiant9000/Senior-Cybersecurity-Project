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


class AssessmentIntakePreviewRequest(BaseModel):
    """Partial intake form payload for live tier preview during onboarding.

    Mirrors the wizard's editable fields. `primary_domain` / `primary_vendor`
    let the preview reflect typed-but-not-yet-synced values without round-
    tripping through the vendor/domain tables.
    """

    name: str | None = None
    industry_label: str | None = None
    primary_state: str | None = None
    employee_range: str | None = None
    revenue_range: str | None = None
    primary_domain: str | None = None
    primary_vendor: str | None = None
    security_controls: dict | None = None
    compliance_frameworks: list[str] | None = None
    data_types: list[str] | None = None
