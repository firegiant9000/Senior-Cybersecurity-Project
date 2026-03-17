"""Pydantic schemas for NVD analytics endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]


class SeverityCount(BaseModel):
    """Count of CVEs for a specific severity level."""

    severity: str
    count: int


class SeverityDistributionResponse(BaseModel):
    """Response for severity distribution analytics."""

    items: list[SeverityCount]
    total_cves: int
    date_from: str | None = None
    date_to: str | None = None


class NvdTimelinePoint(BaseModel):
    """CVE count for a single year."""

    year: int
    count: int


class NvdTimelineResponse(BaseModel):
    """Response for CVE publication timeline analytics."""

    items: list[NvdTimelinePoint]
