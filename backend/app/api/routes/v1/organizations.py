"""Organization routes — v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
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
from app.schemas.assessment_readiness import AssessmentReadinessResponse
from app.schemas.executive_summary import ExecutiveSummaryResponse
from app.schemas.ai_summary import AISummaryResponse
from app.schemas.ai_summary_feedback import FeedbackCreate, FeedbackResponse
from app.schemas.findings import FindingsReport
from app.schemas.findings_snapshot import SnapshotDetail, SnapshotListItem, SnapshotListResponse
from app.schemas.loss_projection import LossProjectionResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationRead,
    OrganizationUpdate,
)
from app.schemas.smb_risk_score import RiskScoreResponse
from app.schemas.vendor_alert import VendorAlertsResponse
from app.services.assessment_readiness import evaluate_readiness
from app.services.executive_summary import ExecutiveSummaryService
from app.services.ai_summary import AISummaryService
from app.services.findings_engine import FindingsEngine
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


@router.get("/mine/readiness", response_model=AssessmentReadinessResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_assessment_readiness(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return assessment readiness status for the current org.

    Checks profile completeness across org fields, vendors, domains, and
    uploads to determine whether the org has enough data for evaluation.
    """
    return await evaluate_readiness(org, db)


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


@router.get("/mine/findings", response_model=FindingsReport)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_findings(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a structured findings report for the current org.

    Synthesizes risk score, vendor CVE matches, assessment readiness, and
    domain reconnaissance (DNS/HTTP/SSL/crt.sh) into categorized findings.
    Requires at least the 'good' readiness tier (all required profile fields set).
    """
    readiness = await evaluate_readiness(org, db)
    if readiness.tier == "minimal":
        raise HTTPException(
            status_code=422,
            detail=(
                "Your organization profile is incomplete. "
                "Please complete all required fields before viewing findings."
            ),
        )
    try:
        return await FindingsEngine(db).build(org, persist=True)
    except Exception:
        logger.exception("Failed to build findings report for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to build findings report")


@router.get("/mine/ai-summary", response_model=AISummaryResponse)
@limiter.limit("5/minute")
async def get_ai_summary(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return an AI-generated executive summary for the current org.

    Uses Google Gemini to synthesize findings into a plain-language narrative.
    Falls back to a template-based summary if Gemini is unavailable or disabled.
    Responses are cached per org for AI_SUMMARY_CACHE_TTL seconds (default 1 hour).
    """
    if not settings.AI_SUMMARY_ENABLED:
        raise HTTPException(status_code=503, detail="AI summary is currently disabled.")
    readiness = await evaluate_readiness(org, db)
    if readiness.tier == "minimal":
        raise HTTPException(
            status_code=422,
            detail=(
                "Your organization profile is incomplete. "
                "Please complete all required fields before generating an AI summary."
            ),
        )
    try:
        return await AISummaryService(db).build(org)
    except Exception:
        logger.exception("Failed to build AI summary for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to generate AI summary")


@router.post("/mine/ai-summary/feedback", response_model=FeedbackResponse, status_code=201)
@limiter.limit("10/minute")
async def submit_ai_summary_feedback(
    request: Request,  # noqa: ARG001
    body: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Submit feedback on an AI-generated summary. One per user per day."""
    from datetime import UTC, datetime, timedelta

    from app.db.ai_summary_feedback import AISummaryFeedback

    # Check for existing feedback from this user today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = await db.execute(
        select(AISummaryFeedback).where(
            AISummaryFeedback.user_id == current_user.id,
            AISummaryFeedback.org_id == org.id,
            AISummaryFeedback.created_at >= today_start,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Feedback already submitted today")

    # Find the most recent snapshot for this org to link the feedback
    from app.db.findings_snapshot import FindingsSnapshot

    snap_result = await db.execute(
        select(FindingsSnapshot.id)
        .where(FindingsSnapshot.org_id == org.id)
        .order_by(FindingsSnapshot.generated_at.desc())
        .limit(1)
    )
    snap_id = snap_result.scalar_one_or_none()

    feedback = AISummaryFeedback(
        org_id=org.id,
        user_id=current_user.id,
        rating=body.rating,
        flag=body.flag,
        comment=body.comment,
        summary_snapshot_id=snap_id,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return FeedbackResponse(
        id=feedback.id,
        rating=feedback.rating,
        flag=feedback.flag,
        comment=feedback.comment,
        created_at=feedback.created_at.isoformat(),
    )


@router.get("/mine/findings/history", response_model=SnapshotListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_findings_history(
    request: Request,  # noqa: ARG001
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a list of recent findings snapshots for trend tracking."""
    from sqlalchemy import func as sa_func

    from app.db.findings_snapshot import FindingsSnapshot

    try:
        count_result = await db.execute(
            select(sa_func.count()).where(FindingsSnapshot.org_id == org.id)
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(FindingsSnapshot)
            .where(FindingsSnapshot.org_id == org.id)
            .order_by(FindingsSnapshot.generated_at.desc())
            .limit(limit)
        )
        snapshots = result.scalars().all()
    except SQLAlchemyError:
        logger.exception("Failed to fetch findings history for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to fetch findings history")

    return SnapshotListResponse(
        items=[
            SnapshotListItem(
                id=s.id,
                generated_at=s.generated_at.isoformat(),
                assessment_tier=s.assessment_tier,
                summary=s.summary,
                data_sources_used=s.data_sources_used,
            )
            for s in snapshots
        ],
        total=total,
    )


@router.get("/mine/findings/history/{snapshot_id}", response_model=SnapshotDetail)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_findings_snapshot(
    request: Request,  # noqa: ARG001
    snapshot_id: int,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a single findings snapshot with full finding details."""
    from app.db.findings_snapshot import FindingsSnapshot

    try:
        result = await db.execute(
            select(FindingsSnapshot).where(
                FindingsSnapshot.id == snapshot_id,
                FindingsSnapshot.org_id == org.id,
            )
        )
        snapshot = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception("Failed to fetch snapshot %s", snapshot_id)
        raise HTTPException(status_code=500, detail="Failed to fetch snapshot")

    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return SnapshotDetail(
        id=snapshot.id,
        org_id=snapshot.org_id,
        generated_at=snapshot.generated_at.isoformat(),
        assessment_tier=snapshot.assessment_tier,
        findings=snapshot.findings,
        summary=snapshot.summary,
        data_sources_used=snapshot.data_sources_used,
    )


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
