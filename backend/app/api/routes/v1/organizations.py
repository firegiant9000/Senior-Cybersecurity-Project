"""Organization routes — v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import get_current_org, require_role
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.organization import Organization
from app.db.user import User
from app.repositories.organization import SqlOrganizationRepository, get_org_repo
from app.schemas.executive_summary import ExecutiveSummaryResponse
from app.schemas.loss_projection import LossProjectionResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationRead,
    OrganizationUpdate,
)
from app.schemas.smb_risk_score import RiskScoreResponse
from app.schemas.vendor_alert import VendorAlertsResponse
from app.services.executive_summary import ExecutiveSummaryService
from app.services.loss_projection import LossProjectionService
from app.services.risk_scoring import calculate_smb_risk_score
from app.services.vendor_alerts import VendorAlertService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=OrganizationRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_organization(
    request: Request,  # noqa: ARG001 — required by slowapi limiter
    body: OrganizationCreate,
    current_user: User = Depends(require_role("admin")),  # noqa: ARG001
    repo: SqlOrganizationRepository = Depends(get_org_repo),
):
    """Create a new organization. Global admin only."""
    try:
        org = await repo.create(body)
    except SQLAlchemyError:
        logger.exception("Failed to create organization")
        raise HTTPException(status_code=500, detail="Failed to create organization")
    return org


@router.get("/", response_model=OrganizationListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_organizations(
    request: Request,  # noqa: ARG001
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(require_role("admin")),  # noqa: ARG001
    repo: SqlOrganizationRepository = Depends(get_org_repo),
):
    """List all organizations (paginated). Global admin only."""
    try:
        items, total = await repo.list_orgs(page, page_size)
    except SQLAlchemyError:
        logger.exception("Failed to list organizations")
        raise HTTPException(status_code=500, detail="Failed to list organizations")
    return OrganizationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[OrganizationRead.model_validate(item) for item in items],
    )


@router.get("/mine/executive-summary", response_model=ExecutiveSummaryResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_executive_summary(
    request: Request,  # noqa: ARG001
    db: AsyncSession = Depends(get_session),
):
    """Return an executive summary of the current threat landscape."""
    try:
        return await ExecutiveSummaryService(db).build()
    except SQLAlchemyError:
        logger.exception("Failed to build executive summary")
        raise HTTPException(status_code=500, detail="Failed to build executive summary")


@router.get("/mine/loss-projection", response_model=LossProjectionResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_loss_projection(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a projected annual cyber-loss estimate for the current org.

    Uses IC3 avg_loss_per_incident filtered by the org's sector and state,
    scaled by an employee-range incident-rate factor.
    """
    try:
        return await LossProjectionService(db).build(org)
    except SQLAlchemyError:
        logger.exception("Failed to build loss projection for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to build loss projection")


@router.get("/mine/risk", response_model=RiskScoreResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_smb_risk_score(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
):
    """Return a parameterized SMB risk score for the current org.

    Combines industry exposure (from IC3 sector-attack weights) and
    employee size factor to produce a 0-100 composite risk score.
    """
    return calculate_smb_risk_score(
        industry_label=org.industry_label,
        employee_range=org.employee_range,
    )


@router.get("/mine/vendor-alerts", response_model=VendorAlertsResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_vendor_alerts(
    request: Request,  # noqa: ARG001
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return exploited vulnerabilities matching the org's vendor stack."""
    try:
        return await VendorAlertService(db).get_alerts(org.id, page, page_size)
    except SQLAlchemyError:
        logger.exception("Failed to fetch vendor alerts for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to fetch vendor alerts")


@router.get("/{org_id}", response_model=OrganizationRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_organization(
    request: Request,  # noqa: ARG001
    org_id: int,
    current_user: User = Depends(require_role("viewer")),
    repo: SqlOrganizationRepository = Depends(get_org_repo),
):
    """Get a single organization. Viewers can access their own org; admins can access any."""
    if current_user.role != "admin" and current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        org = await repo.get_by_id(org_id)
    except SQLAlchemyError:
        logger.exception("Failed to fetch organization %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to fetch organization")
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def update_organization(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: OrganizationUpdate,
    current_user: User = Depends(require_role("member")),
    repo: SqlOrganizationRepository = Depends(get_org_repo),
):
    """Update an organization. Requires global admin or org owner/admin role."""
    if current_user.role != "admin":
        if current_user.org_id != org_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if current_user.org_role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Insufficient organization role",
            )

    try:
        org = await repo.update(org_id, body)
    except SQLAlchemyError:
        logger.exception("Failed to update organization %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to update organization")
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.delete("/{org_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def delete_organization(
    request: Request,  # noqa: ARG001
    org_id: int,
    current_user: User = Depends(require_role("admin")),  # noqa: ARG001
    repo: SqlOrganizationRepository = Depends(get_org_repo),
):
    """Delete an organization. Global admin only. Users' org_id will be set to NULL."""
    try:
        deleted = await repo.delete(org_id)
    except SQLAlchemyError:
        logger.exception("Failed to delete organization %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to delete organization")
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
    return None
