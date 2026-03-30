"""Domain routes — organization domain management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.user import User
from app.repositories.org_domain import SqlOrgDomainRepository, get_domain_repo
from app.schemas.org_domain import OrgDomainCreate, OrgDomainListResponse, OrgDomainRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/organizations/{org_id}/domains", response_model=OrgDomainRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_domain(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: OrgDomainCreate,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgDomainRepository = Depends(get_domain_repo),
    session: AsyncSession = Depends(get_session),
):
    """Add a domain to the organization."""
    await check_org_access(current_user, org_id, session)
    try:
        domain = await repo.create(org_id, current_user.id, body.domain_name)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Domain already exists for this organization")
    except SQLAlchemyError:
        logger.exception("Failed to create domain for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to add domain")
    return domain


@router.get("/organizations/{org_id}/domains", response_model=OrgDomainListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_domains(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgDomainRepository = Depends(get_domain_repo),
    session: AsyncSession = Depends(get_session),
):
    """List domains for an organization (paginated)."""
    await check_org_access(current_user, org_id, session)
    try:
        items, total = await repo.list_domains(org_id, page, page_size)
    except SQLAlchemyError:
        logger.exception("Failed to list domains for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to list domains")
    return OrgDomainListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[OrgDomainRead.model_validate(d) for d in items],
    )


@router.delete("/organizations/{org_id}/domains/{domain_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def delete_domain(
    request: Request,  # noqa: ARG001
    org_id: int,
    domain_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgDomainRepository = Depends(get_domain_repo),
    session: AsyncSession = Depends(get_session),
):
    """Remove a domain from the organization."""
    await check_org_access(current_user, org_id, session)
    try:
        deleted = await repo.delete(domain_id, org_id)
    except SQLAlchemyError:
        logger.exception("Failed to delete domain %s", domain_id)
        raise HTTPException(status_code=500, detail="Failed to delete domain")
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain not found")
    return None
