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
    match_confidence: float | None = None  # 1.0 = exact match, <1.0 = fuzzy similarity score
    in_org_stack: bool = True  # False for "trending elsewhere" rows (no org match)
    # True when the org has a row with both vendor AND product set, and that
    # specific product matches the KEV entry. Drives top-of-list sort so
    # users see CVEs hitting their named products first.
    product_specific: bool = False


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
    # Top KEV entries from CISA's catalog that do NOT match the org's stack —
    # surfaced so users still see what's trending in the wild even if their
    # configured vendors are clean (or before they've added any).
    other_alerts: list[VendorAlert] = []
    page: int
    page_size: int
    unmatched_vendors: list[str]
    reason: str | None = None  # "no_vendors" | "no_matches" | None
    kev_last_ingest_at: datetime | None = None
