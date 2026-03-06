"""NVD routes — v1."""
# pylint: disable=duplicate-code,line-too-long

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.nvd import NvdRepository, get_nvd_repo
from app.schemas.nvd import ALLOWED_SORT_FIELDS, NvdCveListResponse
from app.schemas.nvd_analytics import SeverityCount, SeverityDistributionResponse
from app.services.nvd_analytics import NVDAnalytics

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
    search: Annotated[str | None, Query(description="Search CVE IDs (partial match)")] = None,
    severity: Annotated[
        str | None,
        Query(description="Filter by severity: Critical, High, Medium, Low, Unknown"),
    ] = None,
    *,
    repo: Annotated[NvdRepository, Depends(get_nvd_repo)],
    *,
    repo: Annotated[NvdRepository, Depends(get_nvd_repo)],
) -> NvdCveListResponse:
    """Fetch NVD CVEs from the local database (populated by ingestion)."""
    """Fetch NVD CVEs from the local database (populated by ingestion)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_cves(
        items, total = await repo.list_cves(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            severity=severity,
        )
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return NvdCveListResponse(
            total=total,
            total=total,
            page=page,
            page_size=page_size,
            items=items,
            items=items,
        )
    except ValueError as e:
        logger.error("NVD query validation error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (TypeError, KeyError) as e:
        logger.error("Unexpected error in NVD route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
    except SQLAlchemyError as e:
        logger.error("Database error in NVD route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/analytics/severity-distribution",
    response_model=SeverityDistributionResponse,
)
async def get_severity_distribution(
    date_from: Annotated[date | None, Query(description="Filter: start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[date | None, Query(description="Filter: end date (YYYY-MM-DD)")] = None,
    search: Annotated[str | None, Query(description="Filter by CVE ID (partial match)")] = None,
    severity: Annotated[
        str | None,
        Query(description="Filter by severity: Critical, High, Medium, Low, Unknown"),
    ] = None,
    db: AsyncSession = Depends(get_session),
) -> SeverityDistributionResponse:
    """Get CVE counts grouped by severity level."""
    try:
        analytics = NVDAnalytics(db)
        items = await analytics.get_severity_distribution(
            date_from=date_from,
            date_to=date_to,
            search=search,
            severity=severity,
        )
        severity_items = [SeverityCount(**item) for item in items]
        total = sum(item.count for item in severity_items)
        return SeverityDistributionResponse(
            items=severity_items,
            total_cves=total,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        )
    except SQLAlchemyError as e:
        logger.error("Database error in severity distribution: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
