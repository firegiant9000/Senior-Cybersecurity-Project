"""Domain routes — organization domain management."""

import logging
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.org_domain import OrgDomain
from app.db.user import User
from app.repositories.normalization_log_repo import fire_and_forget_normalization_log
from app.repositories.org_domain import SqlOrgDomainRepository, get_domain_repo
from app.schemas.org_domain import OrgDomainCreate, OrgDomainListResponse, OrgDomainRead
from app.services.domain_checks import run_tier2_checks

EXTERNAL_CHECK_TTL = timedelta(hours=24)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/organizations/{org_id}/domains", response_model=OrgDomainRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_domain(
    request: Request,
    org_id: int,
    body: OrgDomainCreate,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgDomainRepository = Depends(get_domain_repo),
    session: AsyncSession = Depends(get_session),
):
    """Add a domain to the organization."""
    # Capture raw value before Pydantic lowercase+strip normalization
    try:
        raw_body = await request.json()
        raw_domain = raw_body.get("domain_name") or body.domain_name
    except (ValueError, TypeError):
        raw_domain = body.domain_name

    await check_org_access(current_user, org_id, session)
    try:
        domain = await repo.create(org_id, current_user.id, body.domain_name)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Domain already exists for this organization")
    except SQLAlchemyError:
        logger.exception("Failed to create domain for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to add domain")

    fire_and_forget_normalization_log(
        org_id=org_id,
        data_type="domain",
        raw_value=raw_domain,
        normalized_value=domain.domain_name,
        method="pattern",
        created_by=current_user.id,
    )
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


def _dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _dataclass_to_dict(v) for k, v in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_dataclass_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: _dataclass_to_dict(v) for k, v in value.items()}
    return value


@router.get("/organizations/{org_id}/domains/{domain_id}/external-checks")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_external_checks(
    request: Request,  # noqa: ARG001
    org_id: int,
    domain_id: int,
    *,
    force: Annotated[bool, Query()] = False,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Run HIBP, Shodan, and OTX checks for a domain (cached 24h per domain).

    Results are read-only, one-shot lookups. A successful call writes the
    payload to org_domains.external_checks_data and bumps
    external_checks_last_at; subsequent calls within 24h return the cached
    payload without consuming upstream API quota. Pass ``force=true`` to
    bypass the cache — still subject to the per-IP rate limiter.

    Each upstream source returns ``skipped=true`` when its API key is not
    configured, so the route never fails just because one provider is off.
    """
    await check_org_access(current_user, org_id, session)

    result = await session.execute(
        select(OrgDomain).where(OrgDomain.id == domain_id, OrgDomain.org_id == org_id)
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    now = datetime.now(UTC)
    cache_fresh = (
        domain.external_checks_last_at is not None
        and domain.external_checks_data is not None
        and now - domain.external_checks_last_at < EXTERNAL_CHECK_TTL
    )
    if cache_fresh and not force:
        return {
            "domain": domain.domain_name,
            "checked_at": domain.external_checks_last_at.isoformat(),  # type: ignore[union-attr]
            "cached": True,
            "results": domain.external_checks_data,
        }

    crtsh, hibp, shodan, otx = await run_tier2_checks(
        domain.domain_name,
        hibp_api_key=settings.HIBP_API_KEY or None,
        shodan_api_key=settings.SHODAN_API_KEY or None,
        otx_api_key=settings.OTX_API_KEY or None,
    )
    payload = {
        "hibp": _dataclass_to_dict(hibp),
        "shodan": _dataclass_to_dict(shodan),
        "otx": _dataclass_to_dict(otx),
        "crtsh": _dataclass_to_dict(crtsh),
    }

    domain.external_checks_data = payload
    domain.external_checks_last_at = now
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("Failed to persist external-check cache for domain %s", domain_id)
        # Still return live results — caching is best-effort.

    return {
        "domain": domain.domain_name,
        "checked_at": now.isoformat(),
        "cached": False,
        "results": payload,
    }


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
