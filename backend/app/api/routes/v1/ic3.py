"""IC3 routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.repositories.ic3 import SqlIC3Repository, get_ic3_repo
from app.schemas.ic3 import ALLOWED_SORT_FIELDS, IC3IncidentListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
    repo: SqlIC3Repository = Depends(get_ic3_repo),
) -> IC3IncidentListResponse:
    """List IC3 incidents (paginated and sortable)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    items, total = await repo.list_incidents(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return IC3IncidentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
