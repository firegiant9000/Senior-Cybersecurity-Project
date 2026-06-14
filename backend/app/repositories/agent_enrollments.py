"""Repository abstraction for AgentEnrollments (Month 4 Phase 1)."""

# pylint: disable=too-few-public-methods

import logging
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import get_session

logger = logging.getLogger(__name__)


class SqlAgentEnrollmentRepository:
    """Queries AgentEnrollments. Reads are org-scoped except ``get_by_prefix``.

    ``get_by_prefix`` is intentionally *not* org-scoped: token verification only
    has the bearer token, and the org is *derived* from the resolved row. Every
    other read takes an ``org_id`` so an admin can only see/manage their own
    org's agents.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        org_id: int,
        *,
        name: str,
        token_hash: str,
        token_prefix: str,
        scopes: list[str] | None,
        created_by_user_id: int | None,
        expires_at: datetime | None,
    ) -> AgentEnrollment:
        enrollment = AgentEnrollment(
            org_id=org_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self._session.add(enrollment)
        await self._session.commit()
        await self._session.refresh(enrollment)
        return enrollment

    async def get_by_prefix(self, token_prefix: str) -> AgentEnrollment | None:
        """Resolve a token's enrollment by its public prefix (NOT org-scoped)."""
        result = await self._session.execute(
            select(AgentEnrollment).where(AgentEnrollment.token_prefix == token_prefix)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, enrollment_id: int, org_id: int) -> AgentEnrollment | None:
        result = await self._session.execute(
            select(AgentEnrollment).where(
                AgentEnrollment.id == enrollment_id,
                AgentEnrollment.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, org_id: int) -> list[AgentEnrollment]:
        stmt = (
            select(AgentEnrollment)
            .where(AgentEnrollment.org_id == org_id)
            .order_by(AgentEnrollment.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def touch_last_used(self, enrollment: AgentEnrollment, when: datetime) -> None:
        enrollment.last_used_at = when
        await self._session.commit()

    async def set_revoked_at(self, enrollment: AgentEnrollment, when: datetime) -> AgentEnrollment:
        enrollment.revoked_at = when
        await self._session.commit()
        await self._session.refresh(enrollment)
        return enrollment


def get_agent_enrollment_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAgentEnrollmentRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAgentEnrollmentRepository(session)
