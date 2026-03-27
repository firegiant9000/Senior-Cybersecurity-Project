"""Organization routes — v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.dependencies import require_role
from app.core.limiter import limiter
from app.db.user import User
from app.repositories.organization import SqlOrganizationRepository, get_org_repo
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationRead,
    OrganizationUpdate,
)

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
