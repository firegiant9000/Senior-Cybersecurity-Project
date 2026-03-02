"""Pydantic schemas for IC3 incident endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]  # pylint: disable=import-error

# Allowed values for the sort_by query parameter.
ALLOWED_SORT_FIELDS = frozenset({"year", "sector", "state", "loss_amount", "id"})


class IC3IncidentItem(BaseModel):
    """A single IC3 incident record."""

    id: int  # noqa: A003
    year: int
    sector: str
    state: str
    loss_amount: float


class IC3IncidentListResponse(BaseModel):
    """Paginated response for IC3 incident listing endpoints."""

    total: int
    page: int
    page_size: int
    items: list[IC3IncidentItem]
