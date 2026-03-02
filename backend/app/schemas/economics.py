"""Pydantic schemas for Census/BEA economic indicator endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]  # pylint: disable=import-error

# Allowed values for the sort_by query parameter.
ALLOWED_SORT_FIELDS = frozenset({"state", "smb_count", "avg_revenue", "id"})


class EconomicIndicatorItem(BaseModel):
    """A single economic indicator record."""

    id: int  # noqa: A003
    state: str
    smb_count: int
    avg_revenue: float


class EconomicIndicatorListResponse(BaseModel):
    """Paginated response for economic indicator listing endpoints."""

    total: int
    page: int
    page_size: int
    items: list[EconomicIndicatorItem]
