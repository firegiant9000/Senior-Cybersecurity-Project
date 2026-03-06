"""NVD routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.repositories.nvd import NvdRepository, get_nvd_repo
from app.schemas.nvd import ALLOWED_SORT_FIELDS, NvdCveListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/cves", response_model=NvdCveListResponse)
async def list_nvd_cves(
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
    ] = "published_date",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "desc",
    *,
    repo: Annotated[NvdRepository, Depends(get_nvd_repo)],
) -> NvdCveListResponse:
    """Fetch NVD CVEs from the local database (populated by ingestion)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_cves(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return NvdCveListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    except ValueError as e:
        logger.error("NVD query validation error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (TypeError, KeyError) as e:
        logger.error("Unexpected error in NVD route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
