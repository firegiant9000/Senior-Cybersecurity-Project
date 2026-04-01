"""Repository abstraction for OrgDomains."""

# pylint: disable=too-few-public-methods,duplicate-code

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.org_domain import OrgDomain

logger = logging.getLogger(__name__)


class SqlOrgDomainRepository:
    """Queries OrgDomains from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: int, added_by: int | None, domain_name: str) -> OrgDomain:
        domain = OrgDomain(org_id=org_id, added_by=added_by, domain_name=domain_name)
        self._session.add(domain)
        await self._session.commit()
        await self._session.refresh(domain)
        return domain

    async def list_domains(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[OrgDomain], int]:
        stmt = (
            select(OrgDomain)
            .where(OrgDomain.org_id == org_id)
            .order_by(OrgDomain.domain_name)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(OrgDomain.id)).where(OrgDomain.org_id == org_id)
        )
        total = int(total_result.scalar_one())

        return rows, total

    async def delete(self, domain_id: int, org_id: int) -> bool:
        result = await self._session.execute(
            select(OrgDomain).where(OrgDomain.id == domain_id, OrgDomain.org_id == org_id)
        )
        domain = result.scalar_one_or_none()
        if domain is None:
            return False
        await self._session.delete(domain)
        await self._session.commit()
        return True


def get_domain_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgDomainRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgDomainRepository(session)
