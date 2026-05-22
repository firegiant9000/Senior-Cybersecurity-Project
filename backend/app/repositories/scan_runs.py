"""Repository abstraction for ScanRuns."""

# pylint: disable=too-few-public-methods

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.scan_run import ScanRun
from app.schemas.scan_run import ScanRunCreate, ScanRunUpdate

logger = logging.getLogger(__name__)


class SqlScanRunRepository:
    """Queries ScanRuns from the database. All queries are org-scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: int, data: ScanRunCreate) -> ScanRun:
        payload = data.model_dump()
        metadata = payload.pop("metadata", None)
        run = ScanRun(org_id=org_id, scan_metadata=metadata, **payload)
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def get_by_id(self, scan_run_id: int, org_id: int) -> ScanRun | None:
        result = await self._session.execute(
            select(ScanRun).where(ScanRun.id == scan_run_id, ScanRun.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[ScanRun], int]:
        stmt = (
            select(ScanRun)
            .where(ScanRun.org_id == org_id)
            .order_by(ScanRun.started_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int(
            (
                await self._session.execute(
                    select(func.count(ScanRun.id)).where(ScanRun.org_id == org_id)
                )
            ).scalar_one()
        )
        return list(rows), total

    async def update(
        self, scan_run_id: int, org_id: int, data: ScanRunUpdate
    ) -> ScanRun | None:
        run = await self.get_by_id(scan_run_id, org_id)
        if run is None:
            return None
        payload = data.model_dump(exclude_unset=True, exclude_none=True)
        metadata = payload.pop("metadata", None)
        for field, value in payload.items():
            setattr(run, field, value)
        if metadata is not None:
            run.scan_metadata = metadata
        await self._session.commit()
        await self._session.refresh(run)
        return run


def get_scan_run_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlScanRunRepository:
    """Factory used as a dependency in the API layer."""
    return SqlScanRunRepository(session)
