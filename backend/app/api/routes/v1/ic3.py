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
    AttackTypeStats,
    DashboardSummary,
    GeographicHeatmapResponse,
    GeographicThreat,
    IndustryRiskProfile,
    IndustryRiskResponse,
    SectorAttackCombination,
    SectorAttackMatrixResponse,
    TemporalTrend,
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
    except Exception as e:  # pragma: no cover - defensive fallback
        logger.exception("Unhandled error in IC3 incidents route: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Verify DATABASE_URL and PostgreSQL credentials.",
        ) from e


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
    except Exception as e:  # pragma: no cover - defensive fallback
        logger.exception("Unhandled error in IC3 filter options route: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Verify DATABASE_URL and PostgreSQL credentials.",
        ) from e


@router.get("/analytics/attack-types", response_model=AttackTypeListResponse)
async def get_attack_types_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> AttackTypeListResponse:
    """Get attack types ranked by financial impact."""
    try:
        analytics = IC3Analytics(db)
        rows = await analytics.get_attack_types_by_loss(year=year)
        return AttackTypeListResponse(items=[AttackTypeStats(**r) for r in rows], year=year)
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 attack-types analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e


@router.get("/analytics/industry-risk", response_model=IndustryRiskResponse)
async def get_industry_risk_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> IndustryRiskResponse:
    """Get industry/sector risk profile with attack vectors."""
    try:
        analytics = IC3Analytics(db)
        rows = await analytics.get_industry_risk_profile(year=year)
        return IndustryRiskResponse(items=[IndustryRiskProfile(**r) for r in rows], year=year)
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 industry-risk analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e


@router.get("/analytics/geographic-heatmap", response_model=GeographicHeatmapResponse)
async def get_geographic_heatmap_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> GeographicHeatmapResponse:
    """Get geographic threat heatmap by state."""
    try:
        analytics = IC3Analytics(db)
        rows = await analytics.get_geographic_threat_heatmap(year=year)
        return GeographicHeatmapResponse(items=[GeographicThreat(**r) for r in rows], year=year)
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 geographic-heatmap analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e


@router.get("/analytics/temporal-trends", response_model=TemporalTrendResponse)
async def get_temporal_trends_analytics(
    attack_type: Annotated[
        str | None, Query(description="Filter by attack type (optional)")
    ] = None,
    db: AsyncSession = Depends(get_session),
) -> TemporalTrendResponse:
    """Get temporal trends across years."""
    try:
        analytics = IC3Analytics(db)
        rows = await analytics.get_temporal_trends(attack_type=attack_type)
        return TemporalTrendResponse(
            items=[TemporalTrend(**r) for r in rows],
            attack_type=attack_type,
        )
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 temporal-trends analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e


@router.get("/analytics/sector-attack-matrix", response_model=SectorAttackMatrixResponse)
async def get_sector_attack_matrix_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> SectorAttackMatrixResponse:
    """Get sector vs attack type matrix for risk assessment."""
    try:
        analytics = IC3Analytics(db)
        rows = await analytics.get_sector_attack_matrix(year=year)
        return SectorAttackMatrixResponse(
            items=[SectorAttackCombination(**r) for r in rows],
            year=year,
        )
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 sector-attack-matrix analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e


@router.get("/analytics/dashboard-summary", response_model=DashboardSummary)
async def get_dashboard_summary_analytics(
    year: Annotated[int | None, Query(description="Filter by year (optional)")] = None,
    db: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    """Get executive dashboard summary for SMB threat intelligence."""
    try:
        analytics = IC3Analytics(db)
        summary_dict = await analytics.get_summary_dashboard(year=year)
        return DashboardSummary(**summary_dict)
    except Exception as e:  # pragma: no cover
        logger.exception("Error in IC3 dashboard-summary analytics: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.") from e
