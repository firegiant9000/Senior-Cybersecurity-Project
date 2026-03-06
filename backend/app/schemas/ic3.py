"""Pydantic schemas for IC3 incident endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]  # pylint: disable=import-error

# Allowed values for the sort_by query parameter.
ALLOWED_SORT_FIELDS = frozenset({"year", "sector", "state", "loss_amount", "id", "attack_type", "complaint_count", "avg_loss_per_incident"})


class IC3IncidentItem(BaseModel):
    """A single IC3 incident record."""

    id: int  # noqa: A003
    year: int
    attack_type: str
    sector: str
    state: str
    complaint_count: int
    loss_amount: float
    avg_loss_per_incident: float | None = None


class IC3IncidentListResponse(BaseModel):
    """Paginated response for IC3 incident listing endpoints."""

    total: int
    page: int
    page_size: int
    items: list[IC3IncidentItem]
