"""Pydantic schemas for vendor-matched vulnerability alerts."""

from datetime import date, datetime

from pydantic import BaseModel


class VendorAlert(BaseModel):
    vendor_name: str
    org_product: str
    cve_id: str
    kev_product: str
    due_date: date | None
    description: str
    cvss_score: float | None
    severity_label: str  # Critical / High / Medium / Low / Unknown
    risk_score: float | None  # 0-100
    published_date: date | None


class SeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0


class VendorAlertsResponse(BaseModel):
    total_matched: int
    severity_breakdown: SeverityBreakdown
    items: list[VendorAlert]
    page: int
    page_size: int
    unmatched_vendors: list[str]
    reason: str | None = None  # "no_vendors" | "no_matches" | None
    kev_last_ingest_at: datetime | None = None
