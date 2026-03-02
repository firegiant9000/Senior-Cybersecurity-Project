"""Repository abstraction for IC3 incidents."""

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
from app.db.models import IC3Incident
from app.schemas.ic3 import ALLOWED_SORT_FIELDS, IC3IncidentItem

logger = logging.getLogger(__name__)


@runtime_checkable
class IC3Repository(Protocol):
    """Contract for IC3 repository implementations."""

    async def list_incidents(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[IC3IncidentItem], int]:
        """Return (items_for_page, total_count)."""
        ...


class SqlIC3Repository:
    """Queries IC3 incidents from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_incidents(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[IC3IncidentItem], int]:
        """List IC3 incidents from the DB with pagination and sorting."""
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by field: {sort_by!r}")

        sort_column_map = {
            "id": IC3Incident.id,
            "year": IC3Incident.year,
            "sector": IC3Incident.sector,
            "state": IC3Incident.state,
            "loss_amount": IC3Incident.loss_amount,
        }
        sort_col = sort_column_map[sort_by]
        order_expr = (
            sort_col.desc().nullslast()
            if sort_order == "desc"
            else sort_col.asc().nullslast()
        )

        stmt = (
            select(IC3Incident)
            .order_by(order_expr)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        total_stmt = select(func.count(IC3Incident.id))
        total_result = await self._session.execute(total_stmt)
        total = int(total_result.scalar_one())

        items = [
            IC3IncidentItem(
                id=row.id,
                year=row.year,
                sector=row.sector,
                state=row.state,
                loss_amount=row.loss_amount,
            )
            for row in rows
        ]
        return items, total


def get_ic3_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlIC3Repository:
    """Factory used as a dependency in the API layer."""
    return SqlIC3Repository(session)
