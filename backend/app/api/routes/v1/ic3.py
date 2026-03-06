"""IC3 routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.ic3 import ALLOWED_SORT_FIELDS, IC3IncidentItem, IC3IncidentListResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Demo IC3 data (2023-2024 statistics from IC3.gov)
DEMO_IC3_DATA = [
    {"id": 1, "year": 2024, "sector": "Business Email Compromise", "state": "CA", "loss_amount": 2780000000},
    {"id": 2, "year": 2024, "sector": "Ransomware", "state": "TX", "loss_amount": 612360000},
    {"id": 3, "year": 2024, "sector": "Extortion", "state": "NY", "loss_amount": 179000000},
    {"id": 4, "year": 2024, "sector": "Romance Scams", "state": "FL", "loss_amount": 1320000000},
    {"id": 5, "year": 2024, "sector": "Investment Fraud", "state": "IL", "loss_amount": 904000000},
    {"id": 6, "year": 2023, "sector": "Business Email Compromise", "state": "CA", "loss_amount": 2670000000},
    {"id": 7, "year": 2023, "sector": "Ransomware", "state": "TX", "loss_amount": 564000000},
    {"id": 8, "year": 2023, "sector": "Extortion", "state": "NY", "loss_amount": 158000000},
    {"id": 9, "year": 2023, "sector": "Romance Scams", "state": "FL", "loss_amount": 1078000000},
    {"id": 10, "year": 2023, "sector": "Investment Fraud", "state": "IL", "loss_amount": 825000000},
]


@router.get("/incidents", response_model=IC3IncidentListResponse)
async def list_ic3_incidents(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=200, alias="page_size", description="Items per page (max 200)")
    ] = 50,
    sort_by: Annotated[
        str,
        Query(
            alias="sort_by",
            description=f"Sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
        ),
    ] = "year",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "desc",
) -> IC3IncidentListResponse:
    """List IC3 incidents from demo data (paginated and sortable)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    # Sort the data
    reverse = sort_order == "desc"
    sorted_items = sorted(DEMO_IC3_DATA, key=lambda x: x.get(sort_by, 0), reverse=reverse)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    items = [IC3IncidentItem(**item) for item in sorted_items[start:end]]

    return IC3IncidentListResponse(
        total=len(DEMO_IC3_DATA),
        page=page,
        page_size=page_size,
        items=items,
    )
