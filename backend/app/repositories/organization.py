"""Repository abstraction for Organizations."""

import logging
from typing import Protocol, runtime_checkable

from fastapi import Depends  # type: ignore[import-not-found]  # pylint: disable=import-error
from sqlalchemy import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # type: ignore[import-not-found]  # pylint: disable=import-error
)

from app.db.engine import get_session
from app.db.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate

logger = logging.getLogger(__name__)


@runtime_checkable
class OrganizationRepository(Protocol):
    """Contract for Organization repository implementations."""

    async def create(self, data: OrganizationCreate) -> Organization: ...

    async def get_by_id(self, org_id: int) -> Organization | None: ...

    async def list_orgs(
        self, page: int, page_size: int
    ) -> tuple[list[Organization], int]: ...

    async def update(
        self, org_id: int, data: OrganizationUpdate
    ) -> Organization | None: ...

    async def delete(self, org_id: int) -> bool: ...


class SqlOrganizationRepository:
    """Queries Organizations from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: OrganizationCreate) -> Organization:
        org = Organization(**data.model_dump())
        self._session.add(org)
        await self._session.commit()
        await self._session.refresh(org)
        return org

    async def get_by_id(self, org_id: int) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_orgs(
        self, page: int, page_size: int
    ) -> tuple[list[Organization], int]:
        stmt = (
            select(Organization)
            .order_by(Organization.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(Organization.id))
        )
        total = int(total_result.scalar_one())

        return rows, total

    async def update(
        self, org_id: int, data: OrganizationUpdate
    ) -> Organization | None:
        org = await self.get_by_id(org_id)
        if org is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        await self._session.commit()
        await self._session.refresh(org)
        return org

    async def delete(self, org_id: int) -> bool:
        org = await self.get_by_id(org_id)
        if org is None:
            return False
        await self._session.delete(org)
        await self._session.commit()
        return True


def get_org_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrganizationRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrganizationRepository(session)
