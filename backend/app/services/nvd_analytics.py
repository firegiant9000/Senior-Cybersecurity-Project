"""NVD analytics and aggregations for severity distribution."""

import logging
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE

logger = logging.getLogger(__name__)


class NVDAnalytics:
    """Analytics and aggregations for NVD CVE data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_severity_distribution(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """Get CVE counts grouped by severity level.

        Severity is computed from cvss_score using the same thresholds
        as the repository _score_to_label helper, so NULL scores and
        zero scores are bucketed as "Unknown".

        Args:
            date_from: Filter CVEs published on or after this date.
            date_to: Filter CVEs published on or before this date.

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

        if date_from:
            stmt = stmt.where(CVE.published_date >= date_from)
        if date_to:
            stmt = stmt.where(CVE.published_date <= date_to)

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
