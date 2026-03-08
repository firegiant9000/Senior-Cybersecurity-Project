"""IC3 routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.repositories.ic3 import SqlIC3Repository
from app.schemas.ic3 import ALLOWED_SORT_FIELDS, IC3IncidentListResponse
from app.schemas.ic3_analytics import (
    AttackTypeListResponse,
    DashboardSummary,
    GeographicHeatmapResponse,
    IndustryRiskResponse,
    SectorAttackMatrixResponse,
    TemporalTrendResponse,
)
from app.services.ic3_analytics import IC3Analytics

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
    db: AsyncSession = Depends(get_session),
) -> IC3IncidentListResponse:
    """List IC3 incidents from database (paginated and sortable)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    repo = SqlIC3Repository(db)
    items, total = await repo.list_incidents(page, page_size, sort_by, sort_order)

    return IC3IncidentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/analytics/attack-types", response_model=AttackTypeListResponse)
async def get_attack_types_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> AttackTypeListResponse:
    """Get attack types ranked by financial impact."""
    analytics = IC3Analytics(db)
    attack_stats = await analytics.get_attack_types_by_loss(year=year)
    return AttackTypeListResponse(attack_types=attack_stats)


@router.get("/analytics/industry-risk", response_model=IndustryRiskResponse)
async def get_industry_risk_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> IndustryRiskResponse:
    """Get industry/sector risk profile with attack vectors."""
    analytics = IC3Analytics(db)
    risk_profile = await analytics.get_industry_risk_profile(year=year)
    return IndustryRiskResponse(risk_profile=risk_profile)


@router.get("/analytics/geographic-heatmap", response_model=GeographicHeatmapResponse)
async def get_geographic_heatmap_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> GeographicHeatmapResponse:
    """Get geographic threat heatmap by state."""
    analytics = IC3Analytics(db)
    heatmap_data = await analytics.get_geographic_threat_heatmap(year=year)
    return GeographicHeatmapResponse(heatmap=heatmap_data)


@router.get("/analytics/temporal-trends", response_model=TemporalTrendResponse)
async def get_temporal_trends_analytics(
    attack_type: Annotated[
        str | None, Query(description="Filter by attack type (optional)")
    ] = None,
    db: AsyncSession = Depends(get_session),
) -> TemporalTrendResponse:
    """Get temporal trends across years."""
    analytics = IC3Analytics(db)
    trends = await analytics.get_temporal_trends(attack_type=attack_type)
    return TemporalTrendResponse(trends=trends)


@router.get("/analytics/sector-attack-matrix", response_model=SectorAttackMatrixResponse)
async def get_sector_attack_matrix_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> SectorAttackMatrixResponse:
    """Get sector vs attack type matrix for risk assessment."""
    analytics = IC3Analytics(db)
    matrix = await analytics.get_sector_attack_matrix(year=year)
    return SectorAttackMatrixResponse(matrix=matrix)


@router.get("/analytics/dashboard-summary", response_model=DashboardSummary)
async def get_dashboard_summary_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    """Get executive dashboard summary for SMB threat intelligence."""
    analytics = IC3Analytics(db)
    summary_dict = await analytics.get_summary_dashboard(year=year)
    return DashboardSummary(**summary_dict)
