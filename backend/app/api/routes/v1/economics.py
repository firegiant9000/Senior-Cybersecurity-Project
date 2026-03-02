"""Economics routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.repositories.economics import SqlEconomicsRepository, get_economics_repo
from app.schemas.economics import ALLOWED_SORT_FIELDS, EconomicIndicatorListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/indicators", response_model=EconomicIndicatorListResponse)
async def list_economic_indicators(
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
    ] = "state",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "asc",
    repo: SqlEconomicsRepository = Depends(get_economics_repo),
) -> EconomicIndicatorListResponse:
    """List economic indicators stored in the database (paginated and sortable)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    items, total = await repo.list_indicators(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return EconomicIndicatorListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
