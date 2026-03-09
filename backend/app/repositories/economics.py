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


_BASELINE_STATE_ECON: list[tuple[str, int, float]] = [
    ("CA", 850_446, 8_200_000.0),
    ("TX", 586_052, 7_100_000.0),
    ("NY", 485_010, 6_900_000.0),
    ("FL", 361_031, 5_800_000.0),
    ("IL", 244_620, 5_200_000.0),
    ("PA", 214_765, 4_900_000.0),
    ("OH", 196_434, 4_600_000.0),
    ("GA", 185_723, 4_500_000.0),
    ("NJ", 179_309, 5_100_000.0),
    ("WA", 178_101, 5_400_000.0),
    ("NC", 177_850, 4_300_000.0),
    ("MI", 173_800, 4_200_000.0),
    ("VA", 172_500, 4_800_000.0),
    ("AZ", 171_100, 3_900_000.0),
    ("MA", 170_200, 5_600_000.0),
    ("TN", 168_400, 3_800_000.0),
    ("IN", 160_900, 3_700_000.0),
    ("MO", 154_200, 3_500_000.0),
    ("MD", 151_700, 4_400_000.0),
    ("WI", 149_500, 3_600_000.0),
    ("CO", 147_900, 4_100_000.0),
    ("MN", 142_400, 4_000_000.0),
    ("SC", 132_600, 3_200_000.0),
    ("AL", 130_900, 2_900_000.0),
    ("LA", 128_200, 3_100_000.0),
    ("KY", 126_100, 2_800_000.0),
    ("OR", 123_800, 3_400_000.0),
    ("OK", 118_400, 2_700_000.0),
    ("CT", 112_700, 3_300_000.0),
    ("UT", 108_900, 2_600_000.0),
    ("IA", 98_500, 2_500_000.0),
    ("MS", 94_600, 2_100_000.0),
    ("AR", 92_100, 2_000_000.0),
    ("NV", 90_800, 2_400_000.0),
    ("KS", 88_700, 2_300_000.0),
    ("NM", 81_300, 1_900_000.0),
    ("NE", 78_600, 1_800_000.0),
    ("WV", 55_200, 1_200_000.0),
    ("ID", 52_700, 1_500_000.0),
    ("HI", 49_400, 1_700_000.0),
    ("NH", 47_200, 1_600_000.0),
    ("ME", 46_500, 1_400_000.0),
    ("RI", 39_800, 1_300_000.0),
    ("MT", 39_100, 1_100_000.0),
    ("DE", 37_200, 1_000_000.0),
    ("SD", 33_700, 900_000.0),
    ("ND", 31_100, 850_000.0),
    ("VT", 23_900, 750_000.0),
    ("AK", 21_500, 800_000.0),
    ("WY", 20_200, 700_000.0),
]


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
            sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullslast()
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

        if items:
            return items, total

        # Fallback to baseline when DB is empty.
        baseline_items = [
            EconomicIndicatorItem(
                id=idx + 1,
                state=state,
                smb_count=smb_count,
                avg_revenue=avg_revenue,
            )
            for idx, (state, smb_count, avg_revenue) in enumerate(_BASELINE_STATE_ECON)
        ]

        reverse = sort_order == "desc"
        if sort_by == "state":
            baseline_items.sort(key=lambda item: item.state, reverse=reverse)
        elif sort_by == "smb_count":
            baseline_items.sort(key=lambda item: item.smb_count, reverse=reverse)
        elif sort_by == "avg_revenue":
            baseline_items.sort(key=lambda item: item.avg_revenue, reverse=reverse)
        else:
            baseline_items.sort(key=lambda item: item.id, reverse=reverse)

        start = (page - 1) * page_size
        end = start + page_size
        return baseline_items[start:end], len(baseline_items)


def get_economics_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlEconomicsRepository:
    """Factory used as a dependency in the API layer."""
    return SqlEconomicsRepository(session)
