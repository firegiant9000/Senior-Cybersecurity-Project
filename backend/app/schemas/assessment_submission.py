"""Pydantic schemas for assessment submissions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AssessmentStatus(StrEnum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "Under Review"


class AssessmentCompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_contact_name: str = Field(..., min_length=1, max_length=200)
    primary_contact_email: EmailStr
    employee_count: int = Field(..., ge=1)
    annual_revenue_usd: float = Field(..., ge=0)
    critical_assets: list[str] = Field(default_factory=list)


class AssessmentSecurityControls(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfa_enabled: bool
    endpoint_protection: bool
    backup_strategy: str = Field(..., min_length=1, max_length=500)
    incident_response_plan: bool


class AssessmentRiskSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_risks: list[str] = Field(default_factory=list)
    compliance_requirements: list[str] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=2000)


class AssessmentIntakeData(BaseModel):
    """Strict intake payload stored in the `data` column."""

    model_config = ConfigDict(extra="forbid")

    company_profile: AssessmentCompanyProfile
    security_controls: AssessmentSecurityControls
    risk_assessment: AssessmentRiskSection


class AssessmentSubmissionCreate(BaseModel):
    organization_id: int = Field(..., ge=1)
    status: AssessmentStatus = AssessmentStatus.DRAFT
    data: AssessmentIntakeData


class AssessmentSubmissionUpdate(BaseModel):
    status: AssessmentStatus
    data: AssessmentIntakeData


class AssessmentSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str  # noqa: A003
    organization_id: int
    status: AssessmentStatus
    data: AssessmentIntakeData
    version: int
    is_current: bool
    created_at: datetime
    updated_at: datetime


class AssessmentSubmissionHistoryResponse(BaseModel):
    organization_id: int
    submissions: list[AssessmentSubmissionRead]
