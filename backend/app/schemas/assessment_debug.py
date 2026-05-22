"""Schemas for the assessment debug endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.assessment_intake import AssessmentIntakeResponse
from app.schemas.assessment_validation import AssessmentValidationResponse
from app.schemas.findings import FindingsReport


class RawOrgProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # Nullable after Phase B2 — fast-path orgs may have only name + domain.
    industry_label: str | None = None
    ic3_sector: str | None = None
    primary_state: str | None = None
    employee_range: str | None = None
    revenue_range: str | None = None
    logo_url: str | None = None
    primary_domain: str | None = None
    security_controls: dict[str, Any] | None = None
    cloud_providers: list[Any] | None = None
    compliance_frameworks: list[Any] | None = None
    data_types: list[Any] | None = None
    device_count_range: str | None = None
    incident_history: str | None = None
    created_at: datetime
    updated_at: datetime


class FindingsReadinessBlock(BaseModel):
    ready: bool
    current_tier: str
    blocking_reason: str | None = None
    report: FindingsReport | None = None


class DebugAssessmentResponse(BaseModel):
    generated_at: datetime
    org_id: int
    raw_profile: RawOrgProfile
    intake: AssessmentIntakeResponse
    validation: AssessmentValidationResponse
    findings_readiness: FindingsReadinessBlock
