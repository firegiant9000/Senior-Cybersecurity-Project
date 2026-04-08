"""Loss projection service — estimates annual cyber-loss for an organization.

Methodology
-----------
1. Query IC3 historical incidents filtered by the org's ic3_sector and primary_state
   (last 3 available years).  If no rows match sector+state, fall back to sector-only,
   then to all-sector.
2. Compute a complaint-weighted average loss per incident across matched rows.
3. Multiply by an employee-range incident-rate factor that approximates how many
   cyber incidents a company of that size expects per year (derived from Verizon DBIR
   and NIST SMB guidance).
4. Return the projected annual loss together with confidence metadata.

All inputs are aggregate public data (FBI IC3); no proprietary telemetry is used.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EmployeeRange
from app.db.models import IC3Incident
from app.db.organization import Organization
from app.schemas.loss_projection import LossProjectionResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Employee-range → estimated incidents per year
# Based on Verizon DBIR SMB data and NIST guidelines; larger companies have
# broader attack surfaces and appear in IC3 reports at higher rates.
# ---------------------------------------------------------------------------
_INCIDENT_RATE: dict[str, float] = {
    EmployeeRange.SOLO: 0.3,  # <1 incident every 3 years
    EmployeeRange.SMALL: 0.8,  # ~1 incident per year
    EmployeeRange.MEDIUM: 1.5,
    EmployeeRange.LARGE: 3.0,
    EmployeeRange.ENTERPRISE: 5.0,
    EmployeeRange.LARGE_ENTERPRISE: 9.0,
}

_METHODOLOGY = (
    "Projected annual loss is estimated by combining three inputs: "
    "(1) FBI IC3 historical loss data filtered to your organization's "
    "industry sector and state (most recent three available years), using a "
    "complaint-weighted average loss per incident; "
    "(2) an employee-range incident-rate factor derived from Verizon DBIR and NIST "
    "SMB guidance, representing expected cyber incidents per year for a company of "
    "your size; and (3) a fallback hierarchy — sector + state → sector-only → "
    "national average — when regional data are sparse. "
    "Confidence is High when sector-and-state data are available, Medium when only "
    "sector-level data are used, and Low when only national data are available. "
    "All inputs are drawn from publicly available aggregate data. "
    "This estimate is not a guarantee of actual losses."
)


def _fmt_loss(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${round(v / 1_000)}k"
    return f"${v:.0f}"


class LossProjectionService:
    """Builds a LossProjectionResponse for a given organization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(self, org: Organization) -> LossProjectionResponse:
        incident_rate = _INCIDENT_RATE.get(org.employee_range, 1.0)
        if org.employee_range not in _INCIDENT_RATE:
            logger.warning(
                "Unknown employee_range %r for org %s — defaulting incident rate to 1.0",
                org.employee_range,
                org.id,
            )

        # Normalise empty strings to None so the fallback hierarchy works
        # without wasting queries that filter on "".
        sector = org.ic3_sector or None
        state = org.primary_state or None

        # Try sector + state first, then sector-only, then all data.
        avg_loss, complaint_count, year_min, year_max, confidence = await self._query(sector, state)

        if avg_loss is None:
            avg_loss, complaint_count, year_min, year_max, _ = await self._query(sector, None)
            confidence = "Medium"

        if avg_loss is None:
            avg_loss, complaint_count, year_min, year_max, _ = await self._query(None, None)
            confidence = "Low"

        has_data = avg_loss is not None
        if not has_data:
            avg_loss = 0.0

        projected = avg_loss * incident_rate

        year_range: str | None = None
        if year_min and year_max:
            year_range = f"{year_min}–{year_max}" if year_min != year_max else str(year_min)

        return LossProjectionResponse(
            projected_annual_loss=round(projected, 2),
            projected_annual_loss_formatted=_fmt_loss(projected),
            sector=org.ic3_sector,
            state=org.primary_state,
            employee_range=org.employee_range,
            size_multiplier=incident_rate,
            ic3_avg_loss_per_incident=round(avg_loss, 2) if has_data else None,
            ic3_incident_count=complaint_count,
            ic3_data_years=year_range,
            confidence_level=confidence,
            methodology=_METHODOLOGY,
            has_data=has_data,
            generated_at=datetime.now(UTC).isoformat(),
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _query(
        self,
        sector: str | None,
        state: str | None,
    ) -> tuple[float | None, int | None, int | None, int | None, str]:
        """Return (avg_loss, complaint_count, year_min, year_max, confidence).

        Averages avg_loss_per_incident over the most recent 3 IC3 years that
        match the given sector/state filters.
        """
        # Find the three most recent years available for this filter combo.
        year_stmt = select(IC3Incident.year).distinct().order_by(IC3Incident.year.desc()).limit(3)
        if sector is not None:
            year_stmt = year_stmt.where(IC3Incident.sector == sector)
        if state is not None:
            year_stmt = year_stmt.where(IC3Incident.state == state)

        year_result = await self.db.execute(year_stmt)
        years = [row[0] for row in year_result.all()]
        if not years:
            return None, None, None, None, "Low"

        # Aggregate over those years using complaint-weighted average:
        # total_loss / total_complaints gives rows with more complaints
        # proportionally more influence than a naive avg().
        stmt = select(
            (
                func.sum(IC3Incident.loss_amount)
                / func.nullif(func.sum(IC3Incident.complaint_count), 0)
            ).label("avg_loss"),
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.min(IC3Incident.year).label("year_min"),
            func.max(IC3Incident.year).label("year_max"),
        ).where(IC3Incident.year.in_(years))
        if sector is not None:
            stmt = stmt.where(IC3Incident.sector == sector)
        if state is not None:
            stmt = stmt.where(IC3Incident.state == state)

        result = await self.db.execute(stmt)
        row = result.one()
        avg_loss = float(row[0]) if row[0] is not None else None
        complaint_count = int(row[1]) if row[1] is not None else None
        year_min = int(row[2]) if row[2] is not None else None
        year_max = int(row[3]) if row[3] is not None else None

        if avg_loss is None:
            return None, None, None, None, "Low"

        confidence = "High" if (sector and state) else ("Medium" if sector else "Low")
        return avg_loss, complaint_count, year_min, year_max, confidence
