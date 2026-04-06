"""Repository abstraction for the technology vendor catalog."""

import logging

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.technology_vendor import TechnologyVendor
from app.schemas.technology_vendor import TechnologyVendorCreate, TechnologyVendorUpdate

logger = logging.getLogger(__name__)


class SqlTechnologyVendorRepository:
    """Queries the technology vendor catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TechnologyVendorCreate) -> TechnologyVendor:
        vendor = TechnologyVendor(**data.model_dump())
        self._session.add(vendor)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def get_by_id(self, vendor_id: int) -> TechnologyVendor | None:
        result = await self._session.execute(
            select(TechnologyVendor).where(TechnologyVendor.id == vendor_id)
        )
        return result.scalar_one_or_none()

    async def list_vendors(self) -> list[TechnologyVendor]:
        result = await self._session.execute(
            select(TechnologyVendor).order_by(
                TechnologyVendor.name, TechnologyVendor.category, TechnologyVendor.version
            )
        )
        return list(result.scalars().all())

    async def update(self, vendor_id: int, data: TechnologyVendorUpdate) -> TechnologyVendor | None:
        vendor = await self.get_by_id(vendor_id)
        if vendor is None:
            return None
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(vendor, field, value)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def delete(self, vendor_id: int) -> bool:
        vendor = await self.get_by_id(vendor_id)
        if vendor is None:
            return False
        await self._session.delete(vendor)
        await self._session.commit()
        return True


def get_technology_vendor_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlTechnologyVendorRepository:
    """Factory used as a dependency in the API layer."""
    return SqlTechnologyVendorRepository(session)
