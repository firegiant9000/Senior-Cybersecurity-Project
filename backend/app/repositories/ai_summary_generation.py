# pylint: disable=too-few-public-methods,duplicate-code
"""Repository for AI Summary Generation records."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.ai_summary_generation import AISummaryGeneration


class SqlAISummaryGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> AISummaryGeneration:
        row = AISummaryGeneration(**kwargs)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_by_org(
        self, org_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[AISummaryGeneration], int]:
        stmt = (
            select(AISummaryGeneration)
            .where(AISummaryGeneration.org_id == org_id)
            .order_by(AISummaryGeneration.generated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(AISummaryGeneration.id)).where(
                AISummaryGeneration.org_id == org_id
            )
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def get(self, generation_id: int, org_id: int) -> AISummaryGeneration | None:
        result = await self._session.execute(
            select(AISummaryGeneration).where(
                AISummaryGeneration.id == generation_id,
                AISummaryGeneration.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()
