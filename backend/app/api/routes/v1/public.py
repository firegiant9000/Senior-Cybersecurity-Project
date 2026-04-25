"""Public (unauthenticated) aggregate stats for the marketing landing page."""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.enums import IndustryLabel
from app.db.models import CVE, KEV, IC3Incident

logger = logging.getLogger(__name__)

router = APIRouter()


class PublicStatsResponse(BaseModel):
    cve_total: int
    kev_total: int
    ic3_sectors: int
    industries_supported: int


_FALLBACK = PublicStatsResponse(
    cve_total=7000,
    kev_total=1000,
    ic3_sectors=16,
    industries_supported=len(IndustryLabel),
)


@router.get("/public/stats", response_model=PublicStatsResponse)
@limiter.limit("60/minute")
async def public_stats(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> PublicStatsResponse:
    """Aggregate counts for the logged-out landing page. No PII."""
    try:
        cve_total = (await db.execute(select(func.count()).select_from(CVE))).scalar_one()
        kev_total = (await db.execute(select(func.count()).select_from(KEV))).scalar_one()
        ic3_sectors = (
            await db.execute(select(func.count(func.distinct(IC3Incident.sector))))
        ).scalar_one()
    except SQLAlchemyError:
        logger.exception("public_stats query failed, returning fallback")
        return _FALLBACK

    return PublicStatsResponse(
        cve_total=int(cve_total or 0),
        kev_total=int(kev_total or 0),
        ic3_sectors=int(ic3_sectors or 0),
        industries_supported=len(IndustryLabel),
    )
