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


class RiskScoreResponse(BaseModel):
    """Parameterized SMB risk score for the authenticated user's organization."""

    score: float
    industry_exposure: IndustryExposureDetail
    size_factor: SizeFactorDetail
    breakdown: list[ScoreComponent]
    methodology: str
    generated_at: str
