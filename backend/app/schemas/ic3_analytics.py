"""Pydantic schemas for IC3 analytics endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]


class AttackTypeStats(BaseModel):
    """Statistics for a specific attack type."""

    attack_type: str
    total_loss: float
    avg_loss: float
    complaint_count: int


class IndustryRiskProfile(BaseModel):
    """Risk profile for an industry sector."""

    sector: str
    complaint_count: int
    total_loss: float
    avg_loss_per_incident: float


class GeographicThreat(BaseModel):
    """Geographic threat data (state-level)."""

    state: str
    complaint_count: int
    total_loss: float
    avg_loss_per_incident: float


class TemporalTrend(BaseModel):
    """Temporal trend data for forecasting."""

    year: int
    complaint_count: int
    total_loss: float
    avg_loss_per_incident: float


class SectorAttackCombination(BaseModel):
    """Combination of sector and attack type."""

    sector: str
    attack_type: str
    complaint_count: int
    total_loss: float
    avg_loss_per_incident: float


class DashboardSummary(BaseModel):
    """Summary statistics for executive dashboard."""

    total_complaints: int
    total_losses: float
    avg_loss_per_incident: float
    attack_type_count: int
    sector_count: int
    state_count: int


class AttackTypeListResponse(BaseModel):
    """Response for attack type analytics."""

    items: list[AttackTypeStats]
    year: int | None = None


class IndustryRiskResponse(BaseModel):
    """Response for industry risk profile."""

    items: list[IndustryRiskProfile]
    year: int | None = None


class GeographicHeatmapResponse(BaseModel):
    """Response for geographic heatmap data."""

    items: list[GeographicThreat]
    year: int | None = None


class TemporalTrendResponse(BaseModel):
    """Response for temporal trend data."""

    items: list[TemporalTrend]
    attack_type: str | None = None
    sector: str | None = None


class SectorAttackMatrixResponse(BaseModel):
    """Response for sector x attack type matrix."""

    items: list[SectorAttackCombination]
    year: int | None = None
