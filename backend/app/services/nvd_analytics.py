"""NVD analytics and aggregations for severity distribution."""

import logging
from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE

logger = logging.getLogger(__name__)


class NVDAnalytics:
    """Analytics and aggregations for NVD CVE data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    _SEVERITY_SCORE_RANGES: dict[str, tuple[float, float]] = {
        "Critical": (9.0, 10.0),
        "High": (7.0, 8.9),
        "Medium": (4.0, 6.9),
        "Low": (0.1, 3.9),
    }

    async def get_severity_distribution(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        severity: str | None = None,
    ) -> list[dict]:
        """Get CVE counts grouped by severity level.

        Severity is computed from cvss_score using the same thresholds
        as the repository _score_to_label helper, so NULL scores and
        zero scores are bucketed as "Unknown".

        Args:
            date_from: Filter CVEs published on or after this date.
            date_to: Filter CVEs published on or before this date.
            search: Filter CVEs by partial CVE ID match.
            severity: Filter to a single severity level.

        Returns:
            List of dicts with severity and count, ordered by severity rank.
        """
        severity_label = case(
            (CVE.cvss_score >= 9.0, "Critical"),
            (CVE.cvss_score >= 7.0, "High"),
            (CVE.cvss_score >= 4.0, "Medium"),
            (CVE.cvss_score > 0, "Low"),
            else_="Unknown",
        ).label("severity")

        # Use min(cvss_score) as a proxy for ordering: the group with the
        # highest minimum score sorts first (Critical > High > Medium > Low > Unknown).
        # This is an aggregate so it's valid with GROUP BY.
        severity_order = func.min(CVE.cvss_score)

        stmt = select(
            severity_label,
            func.count(CVE.id).label("count"),
        ).group_by(severity_label)

        # Never surface CVEs published in the future (date cap = today).
        stmt = stmt.where((CVE.published_date.is_(None)) | (CVE.published_date <= date.today()))

        if date_from:
            stmt = stmt.where(CVE.published_date >= date_from)
        if date_to:
            stmt = stmt.where(CVE.published_date <= date_to)
        if search:
            stmt = stmt.where(CVE.cve_id.ilike(f"%{search}%"))
        if severity:
            sev_list = [s.strip() for s in severity.split(",") if s.strip()]
            sev_clauses = []
            for sev in sev_list:
                if sev in self._SEVERITY_SCORE_RANGES:
                    lo, hi = self._SEVERITY_SCORE_RANGES[sev]
                    sev_clauses.append((CVE.cvss_score >= lo) & (CVE.cvss_score <= hi))
                elif sev == "Unknown":
                    sev_clauses.append(CVE.cvss_score.is_(None))
            if sev_clauses:
                stmt = stmt.where(or_(*sev_clauses))

        stmt = stmt.order_by(severity_order.desc().nullslast())

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "severity": row[0],
                "count": int(row[1]),
            }
            for row in rows
        ]
