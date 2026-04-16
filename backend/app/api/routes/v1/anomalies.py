"""Anomaly detection routes — v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_org
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.organization import Organization
from app.schemas.anomaly import IC3AnomalyResponse, TrendAnomalyResponse, VendorAnomalyResponse
from app.services.anomaly_detection import AnomalyDetectionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ic3", response_model=IC3AnomalyResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ic3_anomalies(
    request: Request,
    threshold: Annotated[
        float,
        Query(ge=0.5, le=5.0, description="Z-score threshold for flagging anomalies (default 2.0)"),
    ] = 2.0,
    db: AsyncSession = Depends(get_session),
) -> IC3AnomalyResponse:
    """Detect IC3 state-level outliers using cross-sectional z-scores.

    For each (sector, year) group, computes mean and stddev of complaint
    counts and losses across all states. States whose z-score exceeds
    `threshold` are returned as anomalies.
    """
    try:
        svc = AnomalyDetectionService(db)
        items = await svc.get_ic3_anomalies(threshold=threshold)
        return IC3AnomalyResponse(items=items, threshold=threshold, total=len(items))
    except SQLAlchemyError as e:
        logger.error("DB error in /anomalies/ic3: %s", e)
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/trends", response_model=TrendAnomalyResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_trend_anomalies(
    request: Request,
    threshold_pct: Annotated[
        float,
        Query(
            ge=0.1,
            le=10.0,
            description="YoY change threshold as a fraction (default 0.5 = 50%)",
        ),
    ] = 0.5,
    db: AsyncSession = Depends(get_session),
) -> TrendAnomalyResponse:
    """Detect year-over-year spikes or drops in IC3 sector totals.

    Sectors where complaint count or loss amount changed by more than
    `threshold_pct` between consecutive years are flagged.
    """
    try:
        svc = AnomalyDetectionService(db)
        items = await svc.get_trend_anomalies(threshold_pct=threshold_pct)
        return TrendAnomalyResponse(items=items, threshold_pct=threshold_pct)
    except SQLAlchemyError as e:
        logger.error("DB error in /anomalies/trends: %s", e)
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/vendors", response_model=VendorAnomalyResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_vendor_anomalies(
    request: Request,
    threshold: Annotated[
        float,
        Query(ge=0.5, le=5.0, description="Z-score threshold for flagging anomalies (default 2.0)"),
    ] = 2.0,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
) -> VendorAnomalyResponse:
    """Detect vendor KEV exposure anomalies for the current org.

    Compares this org's per-vendor KEV match counts against the
    distribution across all orgs. Vendors whose z-score exceeds
    `threshold` are flagged as high exposure outliers.
    """
    try:
        svc = AnomalyDetectionService(db)
        result = await svc.get_vendor_anomalies(org_id=org.id, threshold=threshold)
        return VendorAnomalyResponse(**result)
    except SQLAlchemyError as e:
        logger.error("DB error in /anomalies/vendors: %s", e)
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Internal server error") from e
