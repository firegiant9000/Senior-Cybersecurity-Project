"""Repository abstraction for NVD CVEs."""

import logging
from datetime import date
from typing import Protocol, runtime_checkable

# Pylint considers repository classes "too few public methods" by design.
# pylint: disable=too-few-public-methods,duplicate-code
from fastapi import Depends  # type: ignore[import-not-found]  # pylint: disable=import-error
from sqlalchemy import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    func,
    or_,
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


_SEVERITY_SCORE_RANGES: dict[str, tuple[float, float]] = {
    "Critical": (9.0, 10.0),
    "High": (7.0, 8.9),
    "Medium": (4.0, 6.9),
    "Low": (0.1, 3.9),
}


@runtime_checkable
class NvdRepository(Protocol):
    """Contract for NVD repository implementations."""

    async def list_cves(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        *,
        search: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[NvdCveItem], int]:
        """Return (items_for_page, total_count)."""
        ...


def _build_severity_clause(severity: str):  # type: ignore[no-untyped-def]
    """Build a combined OR clause for severity filtering."""
    sev_list = [s.strip().capitalize() for s in severity.split(",") if s.strip()]
    clauses = []
    for sev in sev_list:
        if sev in _SEVERITY_SCORE_RANGES:
            lo, hi = _SEVERITY_SCORE_RANGES[sev]
            clauses.append((CVE.cvss_score >= lo) & (CVE.cvss_score <= hi))
        elif sev == "Unknown":
            clauses.append(CVE.cvss_score.is_(None))
    return or_(*clauses) if clauses else None


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
        *,
        search: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[NvdCveItem], int]:
        """List NVD CVEs from the DB with pagination, sorting, and filtering."""
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

        # Build WHERE conditions from filters
        conditions: list = []
        # Never surface CVEs published in the future (date cap = today).
        conditions.append((CVE.published_date.is_(None)) | (CVE.published_date <= date.today()))
        if search:
            conditions.append(
                or_(
                    CVE.cve_id.ilike(f"%{search}%"),
                    CVE.description.ilike(f"%{search}%"),
                )
            )
        if date_from:
            conditions.append(CVE.published_date >= date_from)
        if date_to:
            conditions.append(CVE.published_date <= date_to)
        if severity:
            sev_clause = _build_severity_clause(severity)
            if sev_clause is not None:
                conditions.append(sev_clause)

        stmt = select(CVE)
        for cond in conditions:
            stmt = stmt.where(cond)
        stmt = stmt.order_by(order_expr).limit(page_size).offset((page - 1) * page_size)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        total_stmt = select(func.count(CVE.id))
        for cond in conditions:
            total_stmt = total_stmt.where(cond)
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
                epss_score=row.epss_score,
                epss_percentile=row.epss_percentile,
            )
            for row in rows
        ]
        return items, total

    async def get_by_cve_id(self, cve_id: str) -> CVE | None:
        """Fetch a single CVE row by ID (case-insensitive)."""
        stmt = select(CVE).where(func.upper(CVE.cve_id) == cve_id.upper())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


def get_nvd_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlNvdRepository:
    """Factory used as a dependency in the API layer."""
    return SqlNvdRepository(session)
