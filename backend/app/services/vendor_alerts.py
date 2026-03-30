"""Service for vendor-matched vulnerability alerts."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE, KEV
from app.db.org_vendor import OrgVendor
from app.models.ingest_run import IngestRun
from app.schemas.vendor_alert import (
    SeverityBreakdown,
    VendorAlert,
    VendorAlertsResponse,
)
from app.services.risk_scoring import basic_vuln_risk_score


def _normalize_severity(severity: str | None, cvss: float | None) -> str:
    """Map raw severity / CVSS to a canonical label."""
    if severity:
        canon = severity.strip().capitalize()
        if canon in ("Critical", "High", "Medium", "Low"):
            return canon
    # Fall back to CVSS ranges if severity string is missing/unexpected
    if cvss is not None:
        if cvss >= 9.0:
            return "Critical"
        if cvss >= 7.0:
            return "High"
        if cvss >= 4.0:
            return "Medium"
        return "Low"
    return "Unknown"


class VendorAlertService:
    """Joins org_vendors with KEV catalog to find matched vulnerabilities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_alerts(
        self, org_id: int, page: int = 1, page_size: int = 20
    ) -> VendorAlertsResponse:
        # Check if org has any vendors at all
        vendor_count_result = await self._session.execute(
            select(func.count(OrgVendor.id)).where(OrgVendor.org_id == org_id)
        )
        vendor_count = int(vendor_count_result.scalar_one())

        if vendor_count == 0:
            return VendorAlertsResponse(
                total_matched=0,
                severity_breakdown=SeverityBreakdown(),
                items=[],
                page=page,
                page_size=page_size,
                unmatched_vendors=[],
                reason="no_vendors",
                kev_last_ingest_at=await self._last_kev_ingest(),
            )

        # Core join: org_vendors -> kev on LOWER(vendor) match -> cve for enrichment
        # Product matching: match product when org product is non-empty, else match all
        base_stmt = (
            select(
                OrgVendor.vendor_name,
                OrgVendor.product_name.label("org_product"),
                KEV.cve_id,
                KEV.product.label("kev_product"),
                KEV.due_date,
                CVE.description,
                CVE.cvss_score,
                CVE.severity,
                CVE.published_date,
            )
            .join(KEV, func.lower(KEV.vendor) == func.lower(OrgVendor.vendor_name))
            .join(CVE, CVE.cve_id == KEV.cve_id)
            .where(OrgVendor.org_id == org_id)
            .where(
                or_(
                    OrgVendor.product_name == "",
                    func.lower(KEV.product) == func.lower(OrgVendor.product_name),
                )
            )
        )

        # Total count
        count_result = await self._session.execute(
            select(func.count()).select_from(base_stmt.subquery())
        )
        total_matched = int(count_result.scalar_one())

        if total_matched == 0:
            return VendorAlertsResponse(
                total_matched=0,
                severity_breakdown=SeverityBreakdown(),
                items=[],
                page=page,
                page_size=page_size,
                unmatched_vendors=await self._unmatched_vendors(org_id),
                reason="no_matches",
                kev_last_ingest_at=await self._last_kev_ingest(),
            )

        # Fetch page of results, ordered by CVSS desc (most severe first)
        paginated = (
            base_stmt.order_by(CVE.cvss_score.desc().nulls_last(), KEV.due_date.desc().nulls_last())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(paginated)
        rows = result.all()

        # Build items and severity breakdown
        breakdown = SeverityBreakdown()
        items: list[VendorAlert] = []

        for row in rows:
            sev_label = _normalize_severity(row.severity, row.cvss_score)
            risk = basic_vuln_risk_score(row.cvss_score, exploited=True)
            items.append(
                VendorAlert(
                    vendor_name=row.vendor_name,
                    org_product=row.org_product,
                    cve_id=row.cve_id,
                    kev_product=row.kev_product,
                    due_date=row.due_date,
                    description=row.description or "",
                    cvss_score=row.cvss_score,
                    severity_label=sev_label,
                    risk_score=risk,
                    published_date=row.published_date,
                )
            )

        # Compute severity breakdown over ALL matches (not just current page)
        severity_stmt = (
            select(CVE.severity, CVE.cvss_score)
            .select_from(OrgVendor)
            .join(KEV, func.lower(KEV.vendor) == func.lower(OrgVendor.vendor_name))
            .join(CVE, CVE.cve_id == KEV.cve_id)
            .where(OrgVendor.org_id == org_id)
            .where(
                or_(
                    OrgVendor.product_name == "",
                    func.lower(KEV.product) == func.lower(OrgVendor.product_name),
                )
            )
        )
        sev_result = await self._session.execute(severity_stmt)
        for sev_row in sev_result.all():
            label = _normalize_severity(sev_row.severity, sev_row.cvss_score)
            if label == "Critical":
                breakdown.critical += 1
            elif label == "High":
                breakdown.high += 1
            elif label == "Medium":
                breakdown.medium += 1
            elif label == "Low":
                breakdown.low += 1
            else:
                breakdown.unknown += 1

        return VendorAlertsResponse(
            total_matched=total_matched,
            severity_breakdown=breakdown,
            items=items,
            page=page,
            page_size=page_size,
            unmatched_vendors=await self._unmatched_vendors(org_id),
            reason=None,
            kev_last_ingest_at=await self._last_kev_ingest(),
        )

    async def _unmatched_vendors(self, org_id: int) -> list[str]:
        """Return vendor names from the org that have zero KEV matches."""
        # All org vendor names
        org_vendors_stmt = (
            select(OrgVendor.vendor_name).where(OrgVendor.org_id == org_id).distinct()
        )
        # Vendor names that DO match KEV
        matched_stmt = (
            select(OrgVendor.vendor_name)
            .join(KEV, func.lower(KEV.vendor) == func.lower(OrgVendor.vendor_name))
            .where(OrgVendor.org_id == org_id)
            .distinct()
        )

        all_result = await self._session.execute(org_vendors_stmt)
        matched_result = await self._session.execute(matched_stmt)

        all_vendors = {r[0] for r in all_result.all()}
        matched_vendors = {r[0] for r in matched_result.all()}

        return sorted(all_vendors - matched_vendors)

    async def _last_kev_ingest(self):
        """Query the most recent successful KEV ingest timestamp."""
        stmt = (
            select(IngestRun.finished_at)
            .where(IngestRun.source == "kev", IngestRun.status == "completed")
            .order_by(IngestRun.finished_at.desc().nulls_last())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row
