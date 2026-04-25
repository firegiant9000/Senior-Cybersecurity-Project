"""Onboarding routes — self-service org creation for new users."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.enums import OrgRole
from app.db.membership import Membership
from app.db.organization import Organization
from app.db.user import User
from app.schemas.organization import OrganizationCreate, OrganizationRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/complete", response_model=OrganizationRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def complete_onboarding(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    body: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create an organization and assign the current user as its owner.

    Only allowed for authenticated users who do not yet belong to an org.
    Uses SELECT FOR UPDATE to prevent double-submit race conditions.
    """
    try:
        # Lock the user row to prevent concurrent onboarding attempts
        result = await session.execute(
            select(User).where(User.id == current_user.id).with_for_update()
        )
        locked_user = result.scalar_one()

        existing_membership = await session.execute(
            select(Membership).where(
                Membership.user_id == locked_user.id,
                Membership.status == "active",
            )
        )
        if existing_membership.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail="User already belongs to an organization",
            )

        org = Organization(**body.model_dump())
        session.add(org)
        await session.flush()

        locked_user.org_id = org.id
        locked_user.org_role = str(OrgRole.OWNER)
        # Bump global role so this user can manage their org without admin intervention.
        # New users are created as global="viewer"; org owners need at least "member"
        # for endpoints like PUT /organizations/{id} that gate on require_role("member").
        if locked_user.role == "viewer":
            locked_user.role = "member"
        session.add(
            Membership(
                user_id=locked_user.id,
                org_id=org.id,
                role=str(OrgRole.OWNER),
                status="active",
            )
        )

        await session.commit()
        await session.refresh(org)
    except SQLAlchemyError as exc:
        logger.exception("Failed to complete onboarding")
        raise HTTPException(status_code=500, detail="Failed to create organization") from exc

    return org
