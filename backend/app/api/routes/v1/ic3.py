"""IC3 routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.repositories.ic3 import SqlIC3Repository
from app.schemas.ic3 import ALLOWED_SORT_FIELDS, IC3FilterOptionsResponse, IC3IncidentListResponse
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
    attack_type: Annotated[
        str | None, Query(alias="attack_type", description="Filter by attack type")
    ] = None,
    state: Annotated[str | None, Query(description="Filter by US state code")] = None,
    year: Annotated[int | None, Query(description="Filter by year")] = None,
    db: AsyncSession = Depends(get_session),
) -> IC3IncidentListResponse:
    """List IC3 incidents from database (paginated, sortable, and filterable)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        repo = SqlIC3Repository(db)
        items, total = await repo.list_incidents(
            page,
            page_size,
            sort_by,
            sort_order,
            attack_type=attack_type,
            state=state,
            year=year,
        )

        return IC3IncidentListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    except SQLAlchemyError as e:
        logger.error("Database error in IC3 incidents route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/filter-options", response_model=IC3FilterOptionsResponse)
async def get_ic3_filter_options(
    db: AsyncSession = Depends(get_session),
) -> IC3FilterOptionsResponse:
    """Return distinct values for IC3 filter dropdowns."""
    try:
        repo = SqlIC3Repository(db)
        options = await repo.get_filter_options()
        return IC3FilterOptionsResponse(**options)
    except SQLAlchemyError as e:
        logger.error("Database error in IC3 filter options route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
