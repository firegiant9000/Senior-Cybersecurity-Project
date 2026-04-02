"""Executive summary service — aggregates IC3, KEV, and NVD signals."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE, KEV, IC3Incident
from app.schemas.executive_summary import ExecutiveSummaryResponse, TopThreat

_METHODOLOGY = (
    "This risk score combines three public threat-intelligence sources: "
    "(1) CISA Known Exploited Vulnerabilities (KEV) — CVEs actively exploited in the wild "
    "weighted at 40 %; "
    "(2) FBI Internet Crime Complaint Center (IC3) historical loss data weighted at 30 %; "
    "(3) NIST National Vulnerability Database (NVD) critical-CVE concentration weighted at 20 %; "
    "and (4) year-over-year IC3 complaint growth weighted at 10 %. "
    "All inputs are drawn from publicly available aggregate data; no proprietary telemetry is used."
)

_DISCLAIMER = (
    "This summary is generated from aggregate public threat-intelligence data and does not "
    "reflect your organisation's specific security posture, installed software, or network "
    "configuration. Do not use this score as the sole basis for security decisions. "
    "Consult a qualified cybersecurity professional for organisation-specific assessments."
)


def _fmt_loss(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${round(v / 1_000)}k"
    return f"${v:.0f}"


def _risk_label(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def _compute_risk_score(
    kev_count: int,
    total_loss: float,
    critical_cve_count: int,
    total_cve_count: int,
    complaint_growth_pct: float | None,
) -> float:
    """Return a 0–100 composite threat-landscape risk score."""
    # KEV exploitation prevalence — up to 40 pts (1 000 KEVs ≈ max)
    kev_pts = min(kev_count / 1_000.0, 1.0) * 40.0

    # Financial impact magnitude — up to 30 pts ($10 B ≈ max)
    loss_pts = min(total_loss / 10_000_000_000.0, 1.0) * 30.0

    # Critical-CVE concentration — up to 20 pts (≥ 25 % critical ≈ max)
    cve_ratio = (critical_cve_count / total_cve_count) if total_cve_count > 0 else 0.0
    cve_pts = min(cve_ratio / 0.25, 1.0) * 20.0

    # YoY complaint growth — up to 10 pts (≥ 50 % growth ≈ max)
    if complaint_growth_pct is not None and complaint_growth_pct > 0:
        trend_pts = min(complaint_growth_pct / 50.0, 1.0) * 10.0
    else:
        trend_pts = 0.0

    return min(kev_pts + loss_pts + cve_pts + trend_pts, 100.0)


class ExecutiveSummaryService:
    """Builds an ExecutiveSummaryResponse from live database state."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(self) -> ExecutiveSummaryResponse:
        kev_count, critical_cve_count, total_cve_count = await self._cve_stats()
        total_loss, top_threats_raw, year_min, year_max = await self._ic3_stats()
        complaint_growth_pct = await self._complaint_growth()

        risk_score = _compute_risk_score(
            kev_count,
            total_loss,
            critical_cve_count,
            total_cve_count,
            complaint_growth_pct,
        )

        # Confidence: High if all three sources have data, Medium if two, Low if one.
        sources_populated = sum(
            [
                kev_count > 0,
                total_loss > 0,
                total_cve_count > 0,
            ]
        )
        if sources_populated == 3:
            confidence = "High"
        elif sources_populated == 2:
            confidence = "Medium"
        else:
            confidence = "Low"

        has_data = kev_count > 0 or total_loss > 0 or total_cve_count > 0
        year_range = f"{year_min}–{year_max}" if year_min and year_max else "N/A"

        top_threats = [
            TopThreat(
                name=row["attack_type"],
                complaint_count=row["complaint_count"],
                total_loss=row["total_loss"],
            )
            for row in top_threats_raw
        ]

        return ExecutiveSummaryResponse(
            risk_score=round(risk_score, 1),
            risk_label=_risk_label(risk_score),
            top_threats=top_threats,
            loss_estimate=total_loss,
            loss_estimate_formatted=_fmt_loss(total_loss),
            critical_cve_count=critical_cve_count,
            kev_count=kev_count,
            methodology=_METHODOLOGY,
            confidence_level=confidence,
            disclaimer=_DISCLAIMER,
            has_data=has_data,
            generated_at=datetime.now(UTC).isoformat(),
            data_year_range=year_range,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _cve_stats(self) -> tuple[int, int, int]:
        """Return (kev_count, critical_cve_count, total_cve_count)."""
        kev_result = await self.db.execute(select(func.count(KEV.id)))
        kev_count = kev_result.scalar() or 0

        crit_result = await self.db.execute(select(func.count(CVE.id)).where(CVE.cvss_score >= 9.0))
        critical_cve_count = crit_result.scalar() or 0

        total_result = await self.db.execute(select(func.count(CVE.id)))
        total_cve_count = total_result.scalar() or 0

        return int(kev_count), int(critical_cve_count), int(total_cve_count)

    async def _ic3_stats(
        self,
    ) -> tuple[float, list[dict], int | None, int | None]:
        """Return (total_loss, top_3_attack_types, year_min, year_max)."""
        loss_result = await self.db.execute(select(func.sum(IC3Incident.loss_amount)))
        total_loss = float(loss_result.scalar() or 0.0)

        top_stmt = (
            select(
                IC3Incident.attack_type,
                func.sum(IC3Incident.complaint_count).label("complaint_count"),
                func.sum(IC3Incident.loss_amount).label("total_loss"),
            )
            .group_by(IC3Incident.attack_type)
            .order_by(func.sum(IC3Incident.loss_amount).desc())
            .limit(3)
        )
        top_result = await self.db.execute(top_stmt)
        top_rows = [
            {
                "attack_type": row[0],
                "complaint_count": int(row[1]) if row[1] else 0,
                "total_loss": float(row[2]) if row[2] else 0.0,
            }
            for row in top_result.all()
        ]

        year_stmt = select(
            func.min(IC3Incident.year),
            func.max(IC3Incident.year),
        )
        year_result = await self.db.execute(year_stmt)
        year_row = year_result.one()
        year_min = int(year_row[0]) if year_row[0] else None
        year_max = int(year_row[1]) if year_row[1] else None

        return total_loss, top_rows, year_min, year_max

    async def _complaint_growth(self) -> float | None:
        """Return YoY complaint growth % between the two most recent IC3 years."""
        stmt = (
            select(
                IC3Incident.year,
                func.sum(IC3Incident.complaint_count).label("complaints"),
            )
            .group_by(IC3Incident.year)
            .order_by(IC3Incident.year.desc())
            .limit(2)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        if len(rows) < 2:
            return None
        curr = float(rows[0][1]) if rows[0][1] else 0.0
        prev = float(rows[1][1]) if rows[1][1] else 0.0
        if prev == 0:
            return None
        return ((curr - prev) / prev) * 100.0
