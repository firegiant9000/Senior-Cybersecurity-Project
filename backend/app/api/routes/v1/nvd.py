"""NVD routes — v1."""
# pylint: disable=duplicate-code

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import get_session
from app.repositories.nvd import (
    NvdRepository,
    SqlNvdRepository,
    _iso,
    _score_to_label,
    get_nvd_repo,
)
from app.schemas.nvd import ALLOWED_SORT_FIELDS, NvdCveDetailResponse, NvdCveListResponse
from app.schemas.nvd_analytics import NvdTimelineResponse, SeverityDistributionResponse
from app.services.nvd_analytics import NVDAnalytics

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/cves", response_model=NvdCveListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_nvd_cves(
    request: Request,
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
    date_from: Annotated[date | None, Query(description="Filter: start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[date | None, Query(description="Filter: end date (YYYY-MM-DD)")] = None,
    *,
    repo: Annotated[NvdRepository, Depends(get_nvd_repo)],
) -> NvdCveListResponse:
    """Fetch NVD CVEs from the local database (populated by ingestion)."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot be after date_to")
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_cves(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            severity=severity,
            date_from=date_from,
            date_to=date_to,
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
    except SQLAlchemyError as e:
        logger.error("Database error in NVD route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/cves/{cve_id}", response_model=NvdCveDetailResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_nvd_cve(
    request: Request,  # noqa: ARG001
    cve_id: str,
    *,
    repo: Annotated[SqlNvdRepository, Depends(get_nvd_repo)],
) -> NvdCveDetailResponse:
    """Fetch a single CVE by ID, including EPSS score + percentile."""
    row = await repo.get_by_cve_id(cve_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
    return NvdCveDetailResponse(
        id=row.cve_id.upper(),
        description=row.description or "",
        severity_label=_score_to_label(row.cvss_score),
        severity_score=row.cvss_score,
        published_date=_iso(row.published_date),
        last_modified=None,
        epss_score=row.epss_score,
        epss_percentile=row.epss_percentile,
        epss_fetched_at=row.epss_fetched_at.isoformat() if row.epss_fetched_at else None,
    )


@router.get(
    "/analytics/severity-distribution",
    response_model=SeverityDistributionResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_severity_distribution(
    request: Request,
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
        total = sum(item["count"] for item in items)
        return SeverityDistributionResponse(
            items=items,
            total_cves=total,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        )
    except SQLAlchemyError as e:
        logger.error("Database error in severity distribution: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/analytics/timeline", response_model=NvdTimelineResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_nvd_timeline(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> NvdTimelineResponse:
    """Get CVE publication counts grouped by year."""
    try:
        analytics = NVDAnalytics(db)
        items = await analytics.get_cve_timeline()
        return NvdTimelineResponse(items=items)
    except SQLAlchemyError as e:
        logger.error("Database error in NVD timeline: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
