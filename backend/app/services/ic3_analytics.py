"""IC3 analytics and aggregations for SMB threat dashboard."""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IC3Incident

logger = logging.getLogger(__name__)


class IC3Analytics:
    """Analytics and aggregations for IC3 incident data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_attack_types_by_loss(
        self, year: int | None = None, limit: int = 10
    ) -> list[dict]:
        """Get most expensive attack types by total and average loss.

        Args:
            year: Filter to specific year (None = all years)
            limit: Number of attack types to return

        Returns:
            List of dicts with attack_type, total_loss, avg_loss, complaint_count
        """
        stmt = select(
            IC3Incident.attack_type,
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
            func.sum(IC3Incident.complaint_count).label("complaint_count"),
        ).group_by(IC3Incident.attack_type)

        if year:
            stmt = stmt.where(IC3Incident.year == year)

        stmt = stmt.order_by(func.sum(IC3Incident.loss_amount).desc()).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "attack_type": row[0],
                "total_loss": float(row[1]) if row[1] else 0.0,
                "avg_loss": float(row[2]) if row[2] else 0.0,
                "complaint_count": int(row[3]) if row[3] else 0,
            }
            for row in rows
        ]

    async def get_industry_risk_profile(
        self, year: int | None = None, limit: int = 15
    ) -> list[dict]:
        """Get industry sectors by threat activity (complaints + losses).

        Args:
            year: Filter to specific year (None = all years)
            limit: Number of industries to return

        Returns:
            List of dicts with sector, complaint_count, total_loss, avg_loss_per_incident
        """
        stmt = select(
            IC3Incident.sector,
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
        ).group_by(IC3Incident.sector)

        if year:
            stmt = stmt.where(IC3Incident.year == year)

        stmt = stmt.order_by(func.sum(IC3Incident.complaint_count).desc()).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "sector": row[0],
                "complaint_count": int(row[1]) if row[1] else 0,
                "total_loss": float(row[2]) if row[2] else 0.0,
                "avg_loss_per_incident": float(row[3]) if row[3] else 0.0,
            }
            for row in rows
        ]

    async def get_geographic_threat_heatmap(self, year: int | None = None) -> list[dict]:
        """Get geographic distribution of threats (state-level heatmap data).

        Args:
            year: Filter to specific year (None = aggregated)

        Returns:
            List of dicts with state, complaint_count, total_loss, avg_loss
        """
        stmt = select(
            IC3Incident.state,
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
        ).group_by(IC3Incident.state)

        if year:
            stmt = stmt.where(IC3Incident.year == year)

        stmt = stmt.order_by(func.sum(IC3Incident.loss_amount).desc())

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "state": row[0],
                "complaint_count": int(row[1]) if row[1] else 0,
                "total_loss": float(row[2]) if row[2] else 0.0,
                "avg_loss_per_incident": float(row[3]) if row[3] else 0.0,
            }
            for row in rows
        ]

    async def get_temporal_trends(
        self,
        attack_type: str | None = None,
        sector: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict]:
        """Get incident trends over time for forecasting.

        Args:
            attack_type: Filter to specific attack type (None = all)
            sector: Filter to specific sector (None = all)

        Returns:
            List of dicts with year, complaint_count, total_loss, avg_loss
        """
        stmt = select(
            IC3Incident.year,
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
        ).group_by(IC3Incident.year)

        if attack_type:
            stmt = stmt.where(IC3Incident.attack_type == attack_type)
        if sector:
            stmt = stmt.where(IC3Incident.sector == sector)
        if year_from is not None:
            stmt = stmt.where(IC3Incident.year >= year_from)
        if year_to is not None:
            stmt = stmt.where(IC3Incident.year <= year_to)

        stmt = stmt.order_by(IC3Incident.year)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "year": int(row[0]),
                "complaint_count": int(row[1]) if row[1] else 0,
                "total_loss": float(row[2]) if row[2] else 0.0,
                "avg_loss_per_incident": float(row[3]) if row[3] else 0.0,
            }
            for row in rows
        ]

    async def get_sector_attack_matrix(self, year: int | None = None) -> list[dict]:
        """Get cross-tabulation of sectors vs attack types.

        Args:
            year: Filter to specific year (None = all years)

        Returns:
            List of dicts with sector, attack_type, complaint_count, total_loss, avg_loss
        """
        stmt = select(
            IC3Incident.sector,
            IC3Incident.attack_type,
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
        ).group_by(IC3Incident.sector, IC3Incident.attack_type)

        if year:
            stmt = stmt.where(IC3Incident.year == year)

        stmt = stmt.order_by(func.sum(IC3Incident.loss_amount).desc())

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "sector": row[0],
                "attack_type": row[1],
                "complaint_count": int(row[2]) if row[2] else 0,
                "total_loss": float(row[3]) if row[3] else 0.0,
                "avg_loss_per_incident": float(row[4]) if row[4] else 0.0,
            }
            for row in rows
        ]

    async def get_summary_dashboard(self, year: int | None = None) -> dict:
        """Get summary statistics for executive dashboard.

        Args:
            year: Filter to specific year (None = all years)

        Returns:
            Dict with total_complaints, total_losses, avg_loss, attack_types_count, etc.
        """
        stmt = select(
            func.sum(IC3Incident.complaint_count).label("total_complaints"),
            func.sum(IC3Incident.loss_amount).label("total_loss"),
            func.avg(IC3Incident.avg_loss_per_incident).label("avg_loss"),
            func.count(func.distinct(IC3Incident.attack_type)).label("attack_type_count"),
            func.count(func.distinct(IC3Incident.sector)).label("sector_count"),
            func.count(func.distinct(IC3Incident.state)).label("state_count"),
        )

        if year:
            stmt = stmt.where(IC3Incident.year == year)

        result = await self.db.execute(stmt)
        row = result.one()

        return {
            "total_complaints": int(row[0]) if row[0] else 0,
            "total_losses": float(row[1]) if row[1] else 0.0,
            "avg_loss_per_incident": float(row[2]) if row[2] else 0.0,
            "attack_type_count": int(row[3]),
            "sector_count": int(row[4]),
            "state_count": int(row[5]),
        }
