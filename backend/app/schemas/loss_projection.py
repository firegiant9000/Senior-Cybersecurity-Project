"""Pydantic schemas for the organization loss projection endpoint."""

from pydantic import BaseModel


class LossProjectionResponse(BaseModel):
    """Projected annual cyber-loss for the authenticated user's organization."""

    # Core projection
    projected_annual_loss: float
    projected_annual_loss_formatted: str  # e.g. "$1.2M"

    # Context for the projection — nullable after Phase B2 since orgs can
    # exist with only name + domain. Service swaps None for placeholders.
    sector: str | None = None
    state: str | None = None
    employee_range: str | None = None
    size_multiplier: float  # employee-range scaling factor applied

    # IC3 source signals
    ic3_avg_loss_per_incident: float | None  # weighted avg from IC3 rows matched
    ic3_incident_count: int | None  # total complaints in matched rows
    ic3_data_years: str | None  # e.g. "2021–2023"

    # Trust / provenance
    confidence_level: str  # High | Medium | Low
    methodology: str
    has_data: bool  # False when no IC3 rows matched
    generated_at: str  # ISO 8601
