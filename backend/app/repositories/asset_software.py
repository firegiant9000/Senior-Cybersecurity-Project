"""Repository abstraction for AssetSoftware."""

# pylint: disable=too-few-public-methods

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.asset_software import AssetSoftware
from app.db.engine import get_session
from app.schemas.asset_software import AssetSoftwareCreate

logger = logging.getLogger(__name__)


class SqlAssetSoftwareRepository:
    """Queries AssetSoftware from the database. All queries are org-scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, asset_id: int, org_id: int, data: AssetSoftwareCreate
    ) -> AssetSoftware:
        row = AssetSoftware(asset_id=asset_id, org_id=org_id, **data.model_dump())
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_for_asset(self, asset_id: int, org_id: int) -> list[AssetSoftware]:
        result = await self._session.execute(
            select(AssetSoftware)
            .where(AssetSoftware.asset_id == asset_id, AssetSoftware.org_id == org_id)
            .order_by(AssetSoftware.vendor, AssetSoftware.product)
        )
        return list(result.scalars().all())

    async def list_for_org(
        self,
        org_id: int,
        *,
        vendor: str | None = None,
        product: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AssetSoftware], int]:
        stmt = select(AssetSoftware).where(AssetSoftware.org_id == org_id)
        count_stmt = select(func.count(AssetSoftware.id)).where(
            AssetSoftware.org_id == org_id
        )
        if vendor:
            stmt = stmt.where(func.lower(AssetSoftware.vendor) == vendor.lower())
            count_stmt = count_stmt.where(
                func.lower(AssetSoftware.vendor) == vendor.lower()
            )
        if product:
            stmt = stmt.where(func.lower(AssetSoftware.product) == product.lower())
            count_stmt = count_stmt.where(
                func.lower(AssetSoftware.product) == product.lower()
            )
        stmt = (
            stmt.order_by(AssetSoftware.vendor, AssetSoftware.product)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int((await self._session.execute(count_stmt)).scalar_one())
        return list(rows), total

    async def delete_for_asset(self, asset_id: int, org_id: int) -> int:
        rows = await self.list_for_asset(asset_id, org_id)
        for row in rows:
            await self._session.delete(row)
        await self._session.commit()
        return len(rows)


def get_asset_software_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAssetSoftwareRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAssetSoftwareRepository(session)
