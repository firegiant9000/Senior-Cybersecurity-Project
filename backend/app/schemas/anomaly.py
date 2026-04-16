"""Pydantic schemas for anomaly detection endpoints."""

from pydantic import BaseModel


class IC3Anomaly(BaseModel):
    """A single IC3 anomaly — state outlier within its sector for a given year."""

    sector: str
    state: str
    year: int
    complaint_count: int
    loss_amount: float
    z_score_complaints: float
    z_score_loss: float
    anomaly_type: str  # "complaints", "loss", or "both"


class IC3AnomalyResponse(BaseModel):
    """Response for IC3 anomaly detection."""

    items: list[IC3Anomaly]
    threshold: float
    total: int


class TrendAnomaly(BaseModel):
    """Year-over-year spike or drop in IC3 incidents for a sector."""

    sector: str
    year: int
    complaint_count: int
    loss_amount: float
    prev_complaint_count: int | None
    prev_loss_amount: float | None
    yoy_change_complaints: float | None  # fraction, e.g. 0.75 = 75% increase
    yoy_change_loss: float | None
    flagged: bool


class TrendAnomalyResponse(BaseModel):
    """Response for trend anomaly detection."""

    items: list[TrendAnomaly]
    threshold_pct: float


class VendorExposureAnomaly(BaseModel):
    """Vendor exposure anomaly — org KEV match count vs. global average."""

    vendor_name: str
    kev_match_count: int
    global_avg_matches: float
    z_score: float
    anomaly: bool


class VendorAnomalyResponse(BaseModel):
    """Response for vendor exposure anomaly detection."""

    items: list[VendorExposureAnomaly]
    org_total_matches: int
    global_avg_total: float
    threshold: float
    has_vendors: bool
