"""Repository abstraction for economic indicators (Census/BEA derived)."""

import logging
from typing import Protocol, runtime_checkable

# Pylint considers repository classes "too few public methods" by design.
# pylint: disable=too-few-public-methods,duplicate-code
from fastapi import Depends  # type: ignore[import-not-found]  # pylint: disable=import-error
from sqlalchemy import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # type: ignore[import-not-found]  # pylint: disable=import-error
)

from app.db.engine import get_session
from app.db.models import EconomicIndicator
from app.schemas.economics import (
    ALLOWED_SORT_FIELDS,
    EconomicIndicatorItem,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class EconomicsRepository(Protocol):
    """Contract for economics repository implementations."""

    async def list_indicators(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[EconomicIndicatorItem], int]:
        """Return (items_for_page, total_count)."""
        ...


class SqlEconomicsRepository:
    """Queries economic indicators from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_indicators(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[EconomicIndicatorItem], int]:
        """List economic indicators from the DB with pagination and sorting."""
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by field: {sort_by!r}")

        sort_column_map = {
            "id": EconomicIndicator.id,
            "state": EconomicIndicator.state,
            "smb_count": EconomicIndicator.smb_count,
            "avg_revenue": EconomicIndicator.avg_revenue,
        }
        sort_col = sort_column_map[sort_by]
        order_expr = (
            sort_col.desc().nullslast()
            if sort_order == "desc"
            else sort_col.asc().nullslast()
        )

        stmt = (
            select(EconomicIndicator)
            .order_by(order_expr)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        total_stmt = select(func.count(EconomicIndicator.id))
        total_result = await self._session.execute(total_stmt)
        total = int(total_result.scalar_one())

        items = [
            EconomicIndicatorItem(
                id=row.id,
                state=row.state,
                smb_count=row.smb_count,
                avg_revenue=row.avg_revenue,
            )
            for row in rows
        ]
        return items, total


def get_economics_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlEconomicsRepository:
    """Factory used as a dependency in the API layer."""
    return SqlEconomicsRepository(session)
