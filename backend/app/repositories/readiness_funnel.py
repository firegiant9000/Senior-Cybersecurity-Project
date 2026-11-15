"""Repository for the anonymous readiness funnel counters.

Only aggregate counts per (day, version, step) are stored; nothing about the
visitor is ever persisted.
"""

# pylint: disable=too-few-public-methods

from dataclasses import dataclass
from datetime import date

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.readiness_funnel_count import ReadinessFunnelCount


@dataclass(frozen=True)
class FunnelCountRow:
    """One aggregated counter row."""

    day: date
    version: str
    step: str
    count: int


class SqlReadinessFunnelRepository:
    """Increments and reads funnel counters."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def increment(self, day: date, version: str, step: str) -> None:
        """Atomically add one to the counter, creating it on first use.

        A single ``INSERT .. ON CONFLICT DO UPDATE`` so concurrent requests never
        lose an increment. Does not commit; the caller owns the transaction.
        """
        stmt = (
            postgresql.insert(ReadinessFunnelCount)
            .values(day=day, version=version, step=step, count=1)
            .on_conflict_do_update(
                constraint="uq_readiness_funnel_counts_day_version_step",
                set_={"count": ReadinessFunnelCount.count + 1},
            )
        )
        await self._session.execute(stmt)

    async def counts_between(self, start: date, end: date) -> list[FunnelCountRow]:
        """Counters for ``start <= day <= end``, ordered by day, version, step."""
        result = await self._session.execute(
            select(
                ReadinessFunnelCount.day,
                ReadinessFunnelCount.version,
                ReadinessFunnelCount.step,
                ReadinessFunnelCount.count,
            )
            .where(ReadinessFunnelCount.day >= start, ReadinessFunnelCount.day <= end)
            .order_by(
                ReadinessFunnelCount.day,
                ReadinessFunnelCount.version,
                ReadinessFunnelCount.step,
            )
        )
        return [FunnelCountRow(r.day, r.version, r.step, r.count) for r in result.all()]


def get_readiness_funnel_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlReadinessFunnelRepository:
    """Factory used as a dependency in the API layer."""
    return SqlReadinessFunnelRepository(session)
