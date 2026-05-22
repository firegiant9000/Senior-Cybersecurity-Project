"""Repository abstraction for Assets."""

# pylint: disable=too-few-public-methods,duplicate-code

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.asset import Asset
from app.db.engine import get_session
from app.schemas.asset import AssetCreate, AssetUpdate

logger = logging.getLogger(__name__)


class SqlAssetRepository:
    """Queries Assets from the database. All queries are org-scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: int, data: AssetCreate) -> Asset:
        payload = data.model_dump()
        metadata = payload.pop("metadata", None)
        asset = Asset(org_id=org_id, asset_metadata=metadata, **payload)
        self._session.add(asset)
        await self._session.commit()
        await self._session.refresh(asset)
        return asset

    async def get_by_id(self, asset_id: int, org_id: int) -> Asset | None:
        result = await self._session.execute(
            select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hostname(self, org_id: int, hostname: str) -> Asset | None:
        result = await self._session.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.hostname == hostname)
        )
        return result.scalar_one_or_none()

    async def list_assets(
        self,
        org_id: int,
        page: int,
        page_size: int,
        *,
        is_active: bool | None = None,
        hostname_search: str | None = None,
    ) -> tuple[list[Asset], int]:
        stmt = select(Asset).where(Asset.org_id == org_id)
        count_stmt = select(func.count(Asset.id)).where(Asset.org_id == org_id)
        if is_active is not None:
            stmt = stmt.where(Asset.is_active == is_active)
            count_stmt = count_stmt.where(Asset.is_active == is_active)
        if hostname_search:
            like = f"%{hostname_search.lower()}%"
            stmt = stmt.where(func.lower(Asset.hostname).like(like))
            count_stmt = count_stmt.where(func.lower(Asset.hostname).like(like))
        stmt = (
            stmt.order_by(Asset.hostname).limit(page_size).offset((page - 1) * page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int((await self._session.execute(count_stmt)).scalar_one())
        return list(rows), total

    async def update(self, asset_id: int, org_id: int, data: AssetUpdate) -> Asset | None:
        asset = await self.get_by_id(asset_id, org_id)
        if asset is None:
            return None
        payload = data.model_dump(exclude_unset=True, exclude_none=True)
        metadata = payload.pop("metadata", None)
        for field, value in payload.items():
            setattr(asset, field, value)
        if metadata is not None:
            asset.asset_metadata = metadata
        await self._session.commit()
        await self._session.refresh(asset)
        return asset

    async def set_tags(
        self, asset_id: int, org_id: int, tags: list[str]
    ) -> Asset | None:
        """Replace the tag set on an asset. Tags are trimmed + deduplicated."""
        asset = await self.get_by_id(asset_id, org_id)
        if asset is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            t = " ".join(raw.strip().split()).lower()
            if not t or len(t) > 64 or t in seen:
                continue
            seen.add(t)
            cleaned.append(t)
        asset.tags = cleaned or None
        await self._session.commit()
        await self._session.refresh(asset)
        return asset

    async def delete(self, asset_id: int, org_id: int) -> bool:
        asset = await self.get_by_id(asset_id, org_id)
        if asset is None:
            return False
        await self._session.delete(asset)
        await self._session.commit()
        return True


def get_asset_repo(session: AsyncSession = Depends(get_session)) -> SqlAssetRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAssetRepository(session)
