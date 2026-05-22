"""Organization routes — v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import get_current_org, require_org_role, require_role
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.membership import Membership
from app.db.organization import Organization
from app.db.user import User
from app.repositories.finding_status_repository import (
    ALLOWED_STATUSES,
    SqlFindingStatusRepository,
    get_finding_status_repo,
)
from app.repositories.organization import SqlOrganizationRepository, get_org_repo
from app.schemas.ai_summary import AISummaryResponse
from app.schemas.ai_summary_feedback import FeedbackCreate, FeedbackResponse
from app.schemas.ai_summary_generation import (
    AISummaryGenerationDetail,
    AISummaryGenerationListItem,
    AISummaryGenerationListResponse,
)
from app.schemas.assessment_debug import DebugAssessmentResponse
from app.schemas.assessment_intake import (
    AssessmentIntakePreviewRequest,
    AssessmentIntakeResponse,
)
from app.schemas.assessment_readiness import AssessmentReadinessResponse
from app.schemas.assessment_validation import AssessmentValidationResponse
from app.schemas.executive_summary import ExecutiveSummaryResponse
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
from app.services.ai_summary import AISummaryService
from app.services.assessment_debug import build_assessment_debug_snapshot
from app.services.assessment_intake import (
    IntakeSnapshot,
    evaluate_intake,
    evaluate_intake_preview,
)
from app.services.assessment_readiness import evaluate_readiness
from app.services.assessment_validator import build_response, run_validation
from app.services.executive_summary import ExecutiveSummaryService
from app.services.findings_engine import FindingsEngine
from app.services.loss_projection import LossProjectionService
from app.services.risk_scoring import calculate_smb_risk_score, compute_remediation_credit
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
    _current_user: User = Depends(get_current_user),
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


@router.get("/mine/intake", response_model=AssessmentIntakeResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_assessment_intake(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return graduated assessment intake tier status for the current org.

    Evaluates org completeness across three tiers (basic, enhanced,
    comprehensive) and reports which features each tier unlocks plus
    progress toward the next tier.
    """
    return await evaluate_intake(org, db)


@router.post("/mine/intake-preview", response_model=AssessmentIntakeResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def preview_assessment_intake(
    request: Request,  # noqa: ARG001
    body: AssessmentIntakePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Live tier-progress preview for an in-progress onboarding form.

    Accepts a partial intake payload and returns the same tier evaluation as
    `GET /mine/intake`, but without persisting anything. First-time users
    without an org yet are supported (vendor/domain/upload counts default
    to zero plus optimistic +1 for any typed primary_vendor / primary_domain).
    """
    # Look up the user's existing org so persisted vendor / domain / upload
    # counts feed into the preview. Missing-org is fine — pre-onboarding users
    # haven't created one yet.
    current_org: Organization | None = None
    if current_user.org_id is not None:
        result = await db.execute(
            select(Organization).where(Organization.id == current_user.org_id)
        )
        current_org = result.scalar_one_or_none()

    snap = IntakeSnapshot(
        name=body.name,
        industry_label=body.industry_label,
        primary_state=body.primary_state,
        employee_range=body.employee_range,
        revenue_range=body.revenue_range,
        security_controls=body.security_controls,
        compliance_frameworks=body.compliance_frameworks,
        data_types=body.data_types,
        # Optimistic bumps: a typed primary_vendor / primary_domain counts toward
        # the tier even before the row is created. evaluate_intake_preview merges
        # these with the persisted counts using max().
        vendor_count=1 if (body.primary_vendor and body.primary_vendor.strip()) else 0,
        domain_count=1 if (body.primary_domain and body.primary_domain.strip()) else 0,
    )
    return await evaluate_intake_preview(snap, current_org, db)


@router.get("/mine/validation", response_model=AssessmentValidationResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def validate_assessment(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Run all validation rules against the current org's assessment data.

    Returns structured issues (missing fields, duplicates, conflicts, quality)
    plus a 0-100 quality score. Advisory only — does not block save operations.
    """
    try:
        result = await run_validation(org, db)
    except SQLAlchemyError:
        logger.exception("Failed to run validation for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to run assessment validation")
    return build_response(result)


@router.get("/mine/risk", response_model=RiskScoreResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_smb_risk_score(
    request: Request,  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a parameterized SMB risk score for the current org.

    Combines industry exposure (from IC3 sector-attack weights) and
    employee size factor to produce a 0-100 composite risk score, then
    deducts a capped remediation credit derived from findings the org
    has marked as ``done`` (see PATCH /mine/findings/{stable_key}/status).
    """
    base = calculate_smb_risk_score(
        industry_label=org.industry_label,
        employee_range=org.employee_range,
    )
    done_items = await _done_finding_items(org.id, db)
    credit = compute_remediation_credit(done_items, base.score)
    # Recompute with credit applied so effective_score reflects deduction.
    return calculate_smb_risk_score(
        industry_label=org.industry_label,
        employee_range=org.employee_range,
        remediation_credit=credit,
    )


async def _done_finding_items(org_id: int, db: AsyncSession):
    """Return RemediatedItem records for findings the org has marked done.

    Primary source: the denormalized ``title`` and ``severity`` columns
    on ``finding_statuses`` (populated by PATCH). This makes the credit
    independent of snapshot freshness — every finding the user actually
    clicked contributes regardless of whether a recent snapshot exists.

    Fallback: rows that pre-date migration 029 may have NULL title/severity.
    For those we look up the latest snapshot by stable_key. Anything we
    still can't resolve is included as ``severity='medium'`` so the user
    isn't penalised for old data.
    """
    from app.db.finding_status import FindingStatus
    from app.db.findings_snapshot import FindingsSnapshot
    from app.schemas.smb_risk_score import RemediatedItem

    status_rows = await db.execute(
        select(
            FindingStatus.stable_key,
            FindingStatus.title,
            FindingStatus.severity,
        ).where(
            FindingStatus.org_id == org_id,
            FindingStatus.status == "done",
        )
    )
    rows = status_rows.all()
    if not rows:
        return []

    # First pass: rows with denormalised data go straight in.
    items: list[RemediatedItem] = []
    needs_lookup: dict[str, RemediatedItem] = {}
    for stable_key, title, severity in rows:
        if title and severity:
            items.append(RemediatedItem(stable_key=stable_key, title=title, severity=severity))
        else:
            placeholder = RemediatedItem(
                stable_key=stable_key,
                title=stable_key,  # legible default if snapshot lookup fails
                severity="medium",
            )
            needs_lookup[stable_key] = placeholder

    # Second pass: fill in title/severity from the latest snapshot if we
    # still have unresolved rows (legacy data). Best-effort — if no
    # snapshot exists yet we keep the placeholder so the credit is at
    # least non-zero.
    if needs_lookup:
        snap_row = await db.execute(
            select(FindingsSnapshot.findings)
            .where(FindingsSnapshot.org_id == org_id)
            .order_by(FindingsSnapshot.generated_at.desc())
            .limit(1)
        )
        findings_blob = snap_row.scalar_one_or_none()
        if findings_blob:
            for f in findings_blob:
                key = f.get("stable_key")
                if key in needs_lookup:
                    needs_lookup[key] = RemediatedItem(
                        stable_key=key,
                        title=f.get("title", key),
                        severity=f.get("severity", "medium"),
                    )
        items.extend(needs_lookup.values())

    return items


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
    except SQLAlchemyError as exc:
        logger.exception(
            "Failed to fetch vendor alerts for org %s (%s: %s)",
            org.id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Vendor alerts temporarily unavailable — see server logs",
        )


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
    intake = await evaluate_intake(org, db)
    if intake.current_tier in ("incomplete", "basic"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Your organization profile needs at least Enhanced tier "
                "(add vendors, domains, and security controls) "
                "before viewing findings."
            ),
        )
    try:
        return await FindingsEngine(db).build(org, persist=True)
    except Exception as exc:
        logger.exception("Failed to build findings report for org %s", org.id)
        raise HTTPException(
            status_code=503,
            detail=(
                "Findings service temporarily unavailable. "
                "This usually resolves on retry; if it persists, "
                f"an upstream data source may be failing ({type(exc).__name__})."
            ),
        ) from exc


_ALLOWED_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})


class FindingStatusPatch(BaseModel):
    status: str
    # Frontend forwards these so the row carries enough context to feed
    # the risk-score remediation credit without a snapshot join. Values
    # are normalised + clamped server-side to prevent gaming (a malicious
    # client could otherwise PATCH every key with severity=critical to
    # max out the credit).
    title: str | None = None
    severity: str | None = None


class FindingStatusResponse(BaseModel):
    stable_key: str
    status: str


@router.patch(
    "/mine/findings/{stable_key:path}/status",
    response_model=FindingStatusResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def patch_finding_status(
    request: Request,  # noqa: ARG001
    stable_key: str,
    body: FindingStatusPatch,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    repo: SqlFindingStatusRepository = Depends(get_finding_status_repo),
):
    """Set the user-tracked status of a finding for the current org.

    The ``stable_key`` is the identity emitted alongside ``id`` in the
    findings report — it survives re-ingest, so the marked status persists
    even after the engine regenerates findings with new run-specific IDs.
    """
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )
    # Validate + clamp client-supplied metadata. stable_key column is
    # VARCHAR(255), title is VARCHAR(500); a non-allowlisted severity is
    # rejected outright so the credit calculation can't be inflated.
    if len(stable_key) > 255:
        raise HTTPException(status_code=400, detail="stable_key too long (max 255 chars)")
    severity = body.severity.lower().strip() if body.severity else None
    if severity is not None and severity not in _ALLOWED_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail=f"severity must be one of {sorted(_ALLOWED_SEVERITIES)} or null",
        )
    title = body.title[:500] if body.title else None
    try:
        row = await repo.upsert(
            org_id=org.id,
            stable_key=stable_key,
            status=body.status,
            updated_by=current_user.id,
            title=title,
            severity=severity,
        )
    except SQLAlchemyError:
        logger.exception("Failed to upsert finding status for org %s key %s", org.id, stable_key)
        raise HTTPException(status_code=500, detail="Failed to update finding status")
    return FindingStatusResponse(stable_key=row.stable_key, status=row.status)


@router.get("/mine/debug", response_model=DebugAssessmentResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_assessment_debug(
    request: Request,  # noqa: ARG001
    _user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return a debug snapshot of the assessment pipeline. Org admins and owners only."""
    try:
        return await build_assessment_debug_snapshot(org, db)
    except Exception:
        logger.exception("Failed to build debug snapshot for org %s", org.id)
        raise HTTPException(status_code=500, detail="Failed to build debug snapshot")


@router.get("/mine/ai-summary", response_model=AISummaryResponse)
@limiter.limit("5/minute")
async def get_ai_summary(
    request: Request,  # noqa: ARG001
    force_refresh: bool = Query(default=False),  # noqa: FBT001
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Return an AI-generated executive summary for the current org.

    Uses Google Gemini to synthesize findings into a plain-language narrative.
    Falls back to a template-based summary if Gemini is unavailable or disabled.
    Responses are cached per org for AI_SUMMARY_CACHE_TTL seconds (default 1 hour).
    Pass force_refresh=true to bypass the cache and regenerate immediately.
    """
    if not settings.AI_SUMMARY_ENABLED:
        raise HTTPException(status_code=503, detail="AI summary is currently disabled.")
    intake = await evaluate_intake(org, db)
    if intake.current_tier in ("incomplete", "basic"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Your organization profile needs at least Enhanced tier "
                "(add vendors, domains, and security controls) "
                "before generating an AI summary."
            ),
        )
    try:
        service = AISummaryService(db)
        if force_refresh:
            service.invalidate(org.id)
        return await service.build(org, triggered_by_user_id=current_user.id)
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
    from datetime import UTC, datetime

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

    # Validate generation_id belongs to this org if provided
    generation_id = body.ai_summary_generation_id
    if generation_id is not None:
        from app.db.ai_summary_generation import AISummaryGeneration

        gen_result = await db.execute(
            select(AISummaryGeneration.id).where(
                AISummaryGeneration.id == generation_id,
                AISummaryGeneration.org_id == org.id,
            )
        )
        if gen_result.scalar_one_or_none() is None:
            generation_id = None

    feedback = AISummaryFeedback(
        org_id=org.id,
        user_id=current_user.id,
        rating=body.rating,
        flag=body.flag,
        comment=body.comment,
        ai_summary_generation_id=generation_id,
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


@router.get("/mine/ai-summary/history", response_model=AISummaryGenerationListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ai_summary_history(
    request: Request,  # noqa: ARG001
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    _user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """List AI summary generation history for the current org. Admin/owner only."""
    from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

    repo = SqlAISummaryGenerationRepository(db)
    rows, total = await repo.list_by_org(org.id, limit=limit, offset=offset)
    items = [AISummaryGenerationListItem.model_validate(row) for row in rows]
    return AISummaryGenerationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/mine/ai-summary/history/{generation_id}", response_model=AISummaryGenerationDetail)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_ai_summary_generation(
    request: Request,  # noqa: ARG001
    generation_id: int,
    _user: User = Depends(require_org_role("admin")),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_session),
):
    """Get a single AI summary generation record. Admin/owner only."""
    from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository

    repo = SqlAISummaryGenerationRepository(db)
    row = await repo.get(generation_id, org.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return AISummaryGenerationDetail.model_validate(row)


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
    session: AsyncSession = Depends(get_session),
):
    """Get a single organization. Viewers can access their own org or any org they're a member of; admins can access any."""
    if current_user.role != "admin" and current_user.org_id != org_id:
        # Legacy users.org_id check failed — fall back to Membership table
        result = await session.execute(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.org_id == org_id,
                Membership.status == "active",
            )
        )
        if result.scalar_one_or_none() is None:
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

    if body.industry_label is not None and body.ic3_sector:
        from app.repositories.normalization_log_repo import fire_and_forget_normalization_log

        fire_and_forget_normalization_log(
            org_id=org_id,
            data_type="industry",
            raw_value=str(body.industry_label),
            normalized_value=body.ic3_sector,
            method="exact",
            created_by=current_user.id,
        )

    return org
