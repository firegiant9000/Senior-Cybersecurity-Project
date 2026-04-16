"""Anomaly detection service using IC3 and KEV data.

Uses pure SQL aggregations (avg, stddev_pop) so no extra statistical
dependencies are needed.

Detection methods:
- IC3 cross-sectional z-scores: state vs. sector+year average
- YoY growth flagging: >threshold% change in sector totals year-over-year
- Vendor exposure: org KEV match count vs. global org average
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KEV
from app.db.org_vendor import OrgVendor

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_ic3_anomalies(self, threshold: float = 2.0) -> list[dict]:
        """Detect IC3 state-level anomalies using cross-sectional z-scores.

        For each (sector, year) group, compute mean and stddev of
        complaint_count and loss_amount across all states. Flag any state
        whose z-score exceeds `threshold` in either metric.
        """
        from app.db.models import IC3Incident

        # CTE: per (sector, year) baseline statistics across all states
        sector_stats = (
            select(
                IC3Incident.sector,
                IC3Incident.year,
                func.avg(IC3Incident.complaint_count).label("avg_complaints"),
                func.stddev_pop(IC3Incident.complaint_count).label("std_complaints"),
                func.avg(IC3Incident.loss_amount).label("avg_loss"),
                func.stddev_pop(IC3Incident.loss_amount).label("std_loss"),
            )
            .group_by(IC3Incident.sector, IC3Incident.year)
            .cte("sector_stats")
        )

        z_complaint = func.coalesce(
            (IC3Incident.complaint_count - sector_stats.c.avg_complaints)
            / func.nullif(sector_stats.c.std_complaints, 0),
            0,
        ).label("z_complaints")

        z_loss = func.coalesce(
            (IC3Incident.loss_amount - sector_stats.c.avg_loss)
            / func.nullif(sector_stats.c.std_loss, 0),
            0,
        ).label("z_loss")

        stmt = (
            select(
                IC3Incident.sector,
                IC3Incident.state,
                IC3Incident.year,
                IC3Incident.complaint_count,
                IC3Incident.loss_amount,
                z_complaint,
                z_loss,
            )
            .join(
                sector_stats,
                (IC3Incident.sector == sector_stats.c.sector)
                & (IC3Incident.year == sector_stats.c.year),
            )
            .order_by(func.abs(z_complaint).desc())
        )

        result = await self._db.execute(stmt)
        rows = result.all()

        anomalies = []
        for row in rows:
            zc = float(row[5])
            zl = float(row[6])
            flagged_complaints = abs(zc) >= threshold
            flagged_loss = abs(zl) >= threshold
            if not (flagged_complaints or flagged_loss):
                continue
            if flagged_complaints and flagged_loss:
                anomaly_type = "both"
            elif flagged_complaints:
                anomaly_type = "complaints"
            else:
                anomaly_type = "loss"
            anomalies.append(
                {
                    "sector": row[0],
                    "state": row[1],
                    "year": int(row[2]),
                    "complaint_count": int(row[3]) if row[3] else 0,
                    "loss_amount": float(row[4]) if row[4] else 0.0,
                    "z_score_complaints": round(zc, 3),
                    "z_score_loss": round(zl, 3),
                    "anomaly_type": anomaly_type,
                }
            )

        return anomalies

    async def get_trend_anomalies(self, threshold_pct: float = 0.5) -> list[dict]:
        """Detect year-over-year spikes in IC3 sector totals.

        Flags sectors where complaint_count or loss_amount changed by more
        than `threshold_pct` (e.g. 0.5 = 50%) between consecutive years.
        """
        from app.db.models import IC3Incident

        # Aggregate totals per (sector, year)
        totals_stmt = (
            select(
                IC3Incident.sector,
                IC3Incident.year,
                func.sum(IC3Incident.complaint_count).label("complaints"),
                func.sum(IC3Incident.loss_amount).label("loss"),
            )
            .group_by(IC3Incident.sector, IC3Incident.year)
            .order_by(IC3Incident.sector, IC3Incident.year)
        )

        result = await self._db.execute(totals_stmt)
        rows = result.all()

        # Group by sector then compute YoY in Python (dataset is tiny after aggregation)
        from collections import defaultdict

        by_sector: dict[str, list] = defaultdict(list)
        for row in rows:
            by_sector[row[0]].append(
                {"year": int(row[1]), "complaints": int(row[2] or 0), "loss": float(row[3] or 0.0)}
            )

        output = []
        for sector, entries in by_sector.items():
            entries.sort(key=lambda x: x["year"])
            for i, entry in enumerate(entries):
                prev = entries[i - 1] if i > 0 else None
                yoy_c: float | None = None
                yoy_l: float | None = None
                if prev:
                    if prev["complaints"] > 0:
                        yoy_c = (entry["complaints"] - prev["complaints"]) / prev["complaints"]
                    if prev["loss"] > 0:
                        yoy_l = (entry["loss"] - prev["loss"]) / prev["loss"]

                flagged = (yoy_c is not None and abs(yoy_c) >= threshold_pct) or (
                    yoy_l is not None and abs(yoy_l) >= threshold_pct
                )

                output.append(
                    {
                        "sector": sector,
                        "year": entry["year"],
                        "complaint_count": entry["complaints"],
                        "loss_amount": entry["loss"],
                        "prev_complaint_count": prev["complaints"] if prev else None,
                        "prev_loss_amount": prev["loss"] if prev else None,
                        "yoy_change_complaints": round(yoy_c, 4) if yoy_c is not None else None,
                        "yoy_change_loss": round(yoy_l, 4) if yoy_l is not None else None,
                        "flagged": flagged,
                    }
                )

        # Sort: flagged first, then by abs YoY change
        output.sort(
            key=lambda x: (
                not x["flagged"],
                -(abs(x["yoy_change_complaints"] or 0)),
            )
        )
        return output

    async def get_vendor_anomalies(self, org_id: int, threshold: float = 2.0) -> dict:
        """Detect vendor KEV exposure anomalies for an org vs. global baseline.

        Computes how many KEV matches each org-vendor has, then z-scores
        against the distribution of all org-vendor match counts globally.
        """
        # Count KEV matches per (org_id, vendor_name)
        kev_match_stmt = (
            select(
                OrgVendor.org_id,
                OrgVendor.vendor_name,
                func.count(KEV.id).label("kev_matches"),
            )
            .outerjoin(KEV, func.lower(KEV.vendor) == func.lower(OrgVendor.vendor_name))
            .group_by(OrgVendor.org_id, OrgVendor.vendor_name)
        )

        result = await self._db.execute(kev_match_stmt)
        all_rows = result.all()

        if not all_rows:
            return {
                "items": [],
                "org_total_matches": 0,
                "global_avg_total": 0.0,
                "threshold": threshold,
                "has_vendors": False,
            }

        all_counts = [int(r[2]) for r in all_rows]
        global_avg = sum(all_counts) / len(all_counts)
        variance = sum((c - global_avg) ** 2 for c in all_counts) / len(all_counts)
        global_std = variance**0.5

        org_rows = [r for r in all_rows if r[0] == org_id]
        if not org_rows:
            return {
                "items": [],
                "org_total_matches": 0,
                "global_avg_total": global_avg,
                "threshold": threshold,
                "has_vendors": False,
            }

        items = []
        for row in org_rows:
            count = int(row[2])
            z = (count - global_avg) / global_std if global_std > 0 else 0.0
            items.append(
                {
                    "vendor_name": row[1],
                    "kev_match_count": count,
                    "global_avg_matches": round(global_avg, 2),
                    "z_score": round(z, 3),
                    "anomaly": abs(z) >= threshold,
                }
            )

        items.sort(key=lambda x: abs(x["z_score"]), reverse=True)

        return {
            "items": items,
            "org_total_matches": sum(i["kev_match_count"] for i in items),
            "global_avg_total": round(global_avg * len(org_rows), 2),
            "threshold": threshold,
            "has_vendors": True,
        }
