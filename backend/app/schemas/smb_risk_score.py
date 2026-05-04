"""Pydantic schemas for the SMB parameterized risk score endpoint."""

from pydantic import BaseModel


class SizeFactorDetail(BaseModel):
    employee_range: str
    incident_rate: float
    size_score: float


class AttackExposureItem(BaseModel):
    attack_type: str
    sector_weight: float
    contribution: float


class IndustryExposureDetail(BaseModel):
    sector: str | None
    items: list[AttackExposureItem]
    industry_score: float


class ScoreComponent(BaseModel):
    name: str
    score: float
    weight: float
    weighted_score: float


class RemediatedItem(BaseModel):
    """A finding the user marked as ``done``, surfaced for tooltip display."""

    stable_key: str
    title: str
    severity: str


class RemediationCredit(BaseModel):
    """Risk-score deduction earned by checking off findings as remediated.

    Capped at REMEDIATION_CREDIT_CAP_PCT of the base score so the score
    can't be gamed to zero by marking everything done.
    """

    done_count: int
    raw_points: float  # Sum of severity contributions before cap
    applied_points: float  # Actually deducted (capped)
    items: list[RemediatedItem] = []  # Concrete findings that earned the credit


class RiskScoreResponse(BaseModel):
    """Parameterized SMB risk score for the authenticated user's organization."""

    score: float  # Base composite score (industry × size), pre-credit
    effective_score: float  # ``score - remediation_credit.applied_points``
    remediation_credit: RemediationCredit
    industry_exposure: IndustryExposureDetail
    size_factor: SizeFactorDetail
    breakdown: list[ScoreComponent]
    methodology: str
    generated_at: str
