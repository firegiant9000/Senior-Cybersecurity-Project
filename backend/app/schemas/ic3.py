"""Pydantic schemas for IC3 incident endpoints."""

from pydantic import BaseModel  # type: ignore[import-not-found]  # pylint: disable=import-error

# Mirrored from app.services.data_status.IC3_STATIC_SOURCE_LABEL.
IC3_SOURCE_LABEL = "FBI IC3 2023 annual report (static summary)"

# Allowed values for the sort_by query parameter.
ALLOWED_SORT_FIELDS = frozenset(
    {
        "year",
        "sector",
        "state",
        "loss_amount",
        "id",
        "attack_type",
        "complaint_count",
        "avg_loss_per_incident",
    }
)


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
    source: str = IC3_SOURCE_LABEL


class IC3FilterOptionsResponse(BaseModel):
    """Distinct values available for IC3 filter dropdowns."""

    attack_types: list[str]
    states: list[str]
    years: list[int]
    source: str = IC3_SOURCE_LABEL
