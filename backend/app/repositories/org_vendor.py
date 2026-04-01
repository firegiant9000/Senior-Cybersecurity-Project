"""Repository abstraction for OrgVendors."""

# pylint: disable=too-few-public-methods,duplicate-code

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.org_vendor import OrgVendor
from app.schemas.org_vendor import OrgVendorCreate, OrgVendorUpdate

logger = logging.getLogger(__name__)


class SqlOrgVendorRepository:
    """Queries OrgVendors from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: int, data: OrgVendorCreate) -> OrgVendor:
        vendor = OrgVendor(org_id=org_id, **data.model_dump())
        self._session.add(vendor)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def get_by_id(self, vendor_id: int, org_id: int) -> OrgVendor | None:
        result = await self._session.execute(
            select(OrgVendor).where(OrgVendor.id == vendor_id, OrgVendor.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_vendors(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[OrgVendor], int]:
        stmt = (
            select(OrgVendor)
            .where(OrgVendor.org_id == org_id)
            .order_by(OrgVendor.vendor_name, OrgVendor.product_name)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(OrgVendor.id)).where(OrgVendor.org_id == org_id)
        )
        total = int(total_result.scalar_one())

        return rows, total

    async def update(self, vendor_id: int, org_id: int, data: OrgVendorUpdate) -> OrgVendor | None:
        vendor = await self.get_by_id(vendor_id, org_id)
        if vendor is None:
            return None
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(vendor, field, value)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def delete(self, vendor_id: int, org_id: int) -> bool:
        vendor = await self.get_by_id(vendor_id, org_id)
        if vendor is None:
            return False
        await self._session.delete(vendor)
        await self._session.commit()
        return True

    async def bulk_import(self, org_id: int, rows: list[dict[str, str]]) -> tuple[int, int]:
        """Import vendors in bulk, skipping duplicates.

        Returns (imported_count, skipped_count).
        """
        imported = 0
        skipped = 0
        for row in rows:
            stmt = (
                pg_insert(OrgVendor)
                .values(
                    org_id=org_id,
                    vendor_name=row["vendor_name"],
                    product_name=row.get("product_name", ""),
                )
                .on_conflict_do_nothing(constraint="uq_org_vendor_product")
            )
            result = await self._session.execute(stmt)
            if result.rowcount:  # type: ignore[union-attr]
                imported += 1
            else:
                skipped += 1
        await self._session.commit()
        return imported, skipped


def get_vendor_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgVendorRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgVendorRepository(session)
