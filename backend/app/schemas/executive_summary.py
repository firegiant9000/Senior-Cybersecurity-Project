"""Pydantic schemas for the organization executive summary endpoint."""

from pydantic import BaseModel  # type: ignore[import-not-found]


class TopThreat(BaseModel):
    """A top threat by financial impact."""

    name: str
    complaint_count: int
    total_loss: float


class ExecutiveSummaryResponse(BaseModel):
    """Plain-language executive summary of the current threat landscape."""

    # Core risk signal
    risk_score: float
    risk_label: str  # Low | Medium | High | Critical

    # Threat snapshot
    top_threats: list[TopThreat]
    loss_estimate: float
    loss_estimate_formatted: str  # e.g. "$12.5B"
    critical_cve_count: int
    kev_count: int

    # Provenance / trust signals
    methodology: str
    confidence_level: str  # High | Medium | Low
    disclaimer: str

    # Metadata
    generated_at: str   # ISO 8601
    data_year_range: str  # e.g. "2018–2023"
