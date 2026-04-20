"""Assessment submission routes — v1."""

# pylint: disable=unused-argument

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.user import User
from app.repositories.assessment_submission import (
    SqlAssessmentSubmissionRepository,
    get_assessment_repo,
)
from app.schemas.assessment_submission import (
    AssessmentSubmissionCreate,
    AssessmentSubmissionHistoryResponse,
    AssessmentSubmissionRead,
    AssessmentSubmissionUpdate,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _ensure_org_access(current_user: User, organization_id: int) -> None:
    if current_user.role != "admin" and current_user.org_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/", response_model=AssessmentSubmissionRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_assessment(
    request: Request,  # noqa: ARG001 - required by limiter
    body: AssessmentSubmissionCreate,
    current_user: User = Depends(get_current_user),
    repo: SqlAssessmentSubmissionRepository = Depends(get_assessment_repo),
):
    """Create an initial assessment submission for an organization."""
    _ensure_org_access(current_user, body.organization_id)
    try:
        return await repo.create_initial(body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Failed to create assessment") from exc


@router.get("/{org_id}", response_model=AssessmentSubmissionRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_current_assessment(
    request: Request,  # noqa: ARG001 - required by limiter
    org_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlAssessmentSubmissionRepository = Depends(get_assessment_repo),
):
    """Retrieve the current assessment submission for an organization."""
    _ensure_org_access(current_user, org_id)
    try:
        row = await repo.get_current_by_org(org_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch assessment") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return row


@router.get("/{org_id}/history", response_model=AssessmentSubmissionHistoryResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_assessment_history(
    request: Request,  # noqa: ARG001 - required by limiter
    org_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlAssessmentSubmissionRepository = Depends(get_assessment_repo),
):
    """List all historical assessment versions for an organization."""
    _ensure_org_access(current_user, org_id)
    try:
        rows = await repo.get_history_by_org(org_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch assessment history") from exc
    return AssessmentSubmissionHistoryResponse(organization_id=org_id, submissions=rows)


@router.put("/{assessment_id}", response_model=AssessmentSubmissionRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def update_assessment(
    request: Request,  # noqa: ARG001 - required by limiter
    assessment_id: str,
    body: AssessmentSubmissionUpdate,
    current_user: User = Depends(get_current_user),
    repo: SqlAssessmentSubmissionRepository = Depends(get_assessment_repo),
):
    """Create a new immutable assessment version from an existing one."""
    existing = await repo.get_by_id(assessment_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _ensure_org_access(current_user, existing.organization_id)
    try:
        return await repo.create_new_version(assessment_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Failed to update assessment") from exc


@router.delete("/{assessment_id}", response_model=AssessmentSubmissionRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def delete_assessment(
    request: Request,  # noqa: ARG001 - required by limiter
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    repo: SqlAssessmentSubmissionRepository = Depends(get_assessment_repo),
):
    """Soft delete a specific assessment version."""
    existing = await repo.get_by_id(assessment_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _ensure_org_access(current_user, existing.organization_id)
    try:
        deleted = await repo.soft_delete(assessment_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Failed to delete assessment") from exc
    if deleted is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return deleted
