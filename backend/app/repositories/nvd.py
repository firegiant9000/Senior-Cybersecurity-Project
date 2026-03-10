"""Repository abstraction for NVD CVEs."""

import logging
from datetime import date
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
from app.db.models import CVE
from app.schemas.nvd import ALLOWED_SORT_FIELDS, NvdCveItem
from app.schemas.vulnerability import SeverityLabel

logger = logging.getLogger(__name__)


def _score_to_label(score: float | None) -> SeverityLabel | None:
    if score is None:
        return None
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    if score > 0:
        return "Low"
    return "Unknown"


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


@runtime_checkable
class NvdRepository(Protocol):
    """Contract for NVD repository implementations."""

    async def list_cves(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[NvdCveItem], int]:
        """Return (items_for_page, total_count)."""
        ...


class SqlNvdRepository:
    """Queries CVEs from the database (populated from NVD)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_cves(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[NvdCveItem], int]:
        """List NVD CVEs from the DB with pagination and sorting."""
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by field: {sort_by!r}")

        sort_column_map = {
            "id": CVE.cve_id,
            "severity_score": CVE.cvss_score,
            "published_date": CVE.published_date,
        }
        sort_col = sort_column_map[sort_by]
        order_expr = (
            sort_col.desc().nullslast() if sort_order == "desc" else sort_col.asc().nullslast()
        )

        stmt = select(CVE).order_by(order_expr).limit(page_size).offset((page - 1) * page_size)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        total_stmt = select(func.count(CVE.id))
        total_result = await self._session.execute(total_stmt)
        total = int(total_result.scalar_one())

        items = [
            NvdCveItem(
                id=row.cve_id.upper(),
                description=row.description or "",
                severity_label=_score_to_label(row.cvss_score),
                severity_score=row.cvss_score,
                published_date=_iso(row.published_date),
                last_modified=None,
            )
            for row in rows
        ]
        return items, total


def get_nvd_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlNvdRepository:
    """Factory used as a dependency in the API layer."""
    return SqlNvdRepository(session)
