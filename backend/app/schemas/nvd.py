"""Pydantic schemas for NVD CVE endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]  # pylint: disable=import-error

from app.schemas.vulnerability import SeverityLabel

# Allowed values for the sort_by query parameter.
ALLOWED_SORT_FIELDS = frozenset({"published_date", "severity_score", "id"})


class NvdCveItem(BaseModel):
    """A single CVE record from NVD."""

    id: str  # noqa: A003  CVE ID, e.g. "CVE-2021-44228"
    description: str
    severity_label: SeverityLabel | None
    severity_score: float | None
    published_date: str | None  # ISO YYYY-MM-DD NVD publication date
    last_modified: str | None  # ISO YYYY-MM-DD NVD last-modified date
    epss_score: float | None = None  # 30-day exploitation probability (0–1)
    epss_percentile: float | None = None  # 0–1 percentile rank vs. all scored CVEs


class NvdCveListResponse(BaseModel):
    """Paginated response for NVD CVE listing endpoints."""

    total: int
    page: int
    page_size: int
    items: list[NvdCveItem]


class NvdCveDetailResponse(NvdCveItem):
    """Single-CVE response with EPSS metadata."""

    epss_fetched_at: str | None = None
