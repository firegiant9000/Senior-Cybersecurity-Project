"""Public (unauthenticated) aggregate stats for the marketing landing page."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.core.public_readiness import require_public_readiness
from app.db.engine import get_session
from app.db.enums import IndustryLabel
from app.db.models import CVE, KEV, IC3Incident
from app.services.domain_checks import normalize_hostname
from app.services.public_domain_check import EXPLANATIONS, check_public_domain

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


class DomainCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(max_length=1024)


class DomainCheckResponse(BaseModel):
    status: Literal["ok", "domain_not_found", "unavailable"]
    spf_found: bool | None
    dmarc_found: bool | None
    dmarc_policy: Literal["none", "quarantine", "reject"] | None
    rating: Literal["protected", "monitoring_only", "spoofable"] | None
    explanation: str


@router.post(
    "/public/domain-check",
    response_model=DomainCheckResponse,
    dependencies=[Depends(require_public_readiness)],
)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_DOMAIN_CHECK)
async def public_domain_check(request: Request, body: DomainCheckRequest) -> DomainCheckResponse:
    """DNS-only SPF/DMARC check for the logged-out readiness page. Never echoes or logs the domain."""
    host = normalize_hostname(body.domain)
    if host is None:
        raise HTTPException(status_code=422, detail="Enter a domain name such as example.com.")
    result = await check_public_domain(host)
    return DomainCheckResponse(
        status=result.status,
        spf_found=result.spf_found,
        dmarc_found=result.dmarc_found,
        dmarc_policy=result.dmarc_policy,
        rating=result.rating,
        explanation=EXPLANATIONS[result.rating if result.rating else result.status],
    )
