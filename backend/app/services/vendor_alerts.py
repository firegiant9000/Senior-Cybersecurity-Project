"""Service for vendor-matched vulnerability alerts."""

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVE, KEV
from app.db.org_vendor import OrgVendor
from app.models.ingest_run import IngestRun
from app.repositories.normalization_log_repo import fire_and_forget_normalization_log
from app.schemas.vendor_alert import (
    SeverityBreakdown,
    VendorAlert,
    VendorAlertsResponse,
)
from app.services.risk_scoring import basic_vuln_risk_score

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 0.75

# Common cloud/SaaS display names that don't appear in the KEV catalog under those names.
# Maps lowercase org-entered name → canonical KEV vendor name.
VENDOR_ALIASES: dict[str, str] = {
    "aws": "Amazon",
    "amazon aws": "Amazon",
    "azure": "Microsoft",
    "azure ad": "Microsoft",
    "microsoft azure": "Microsoft",
    "microsoft 365": "Microsoft",
    "office 365": "Microsoft",
    "ms 365": "Microsoft",
    "gcp": "Google",
    "google cloud": "Google",
    "google cloud platform": "Google",
    "google workspace": "Google",
    "g suite": "Google",
}


def _compute_severity_breakdown(combined: list[dict]) -> SeverityBreakdown:
    breakdown = SeverityBreakdown()
    for r in combined:
        label = _normalize_severity(r["severity"], r["cvss_score"])
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
    return breakdown


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

    async def _run_alias_pass(self, org_id: int, unmatched: set[str]) -> list:
        """Exact-match pass using VENDOR_ALIASES for cloud/SaaS display names."""
        rows: list = []
        alias_map = {v: VENDOR_ALIASES[v.lower()] for v in unmatched if v.lower() in VENDOR_ALIASES}
        for org_name, kev_name in alias_map.items():
            stmt = (
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
                .join(KEV, func.lower(KEV.vendor) == kev_name.lower())
                .join(CVE, CVE.cve_id == KEV.cve_id)
                .where(OrgVendor.org_id == org_id)
                .where(OrgVendor.vendor_name == org_name)
                .where(
                    or_(
                        OrgVendor.product_name == "",
                        func.lower(KEV.product) == func.lower(OrgVendor.product_name),
                    )
                )
            )
            matched = (await self._session.execute(stmt)).all()
            rows.extend(matched)
            if matched:
                fire_and_forget_normalization_log(
                    org_id=org_id,
                    data_type="vendor",
                    raw_value=org_name,
                    normalized_value=kev_name,
                    method="alias",
                    confidence=1.0,
                )
        return rows

    async def _run_fuzzy_pass(self, org_id: int, unmatched: set[str]) -> list:
        """Trigram-based fuzzy match. Degrades to [] if pg_trgm is unavailable."""
        if not unmatched:
            return []
        stmt = (
            select(
                OrgVendor.vendor_name,
                OrgVendor.product_name.label("org_product"),
                KEV.vendor.label("kev_vendor"),
                KEV.cve_id,
                KEV.product.label("kev_product"),
                KEV.due_date,
                CVE.description,
                CVE.cvss_score,
                CVE.severity,
                CVE.published_date,
                func.similarity(KEV.vendor, OrgVendor.vendor_name).label("score"),
            )
            .join(KEV, KEV.vendor.op("%")(OrgVendor.vendor_name))
            .join(CVE, CVE.cve_id == KEV.cve_id)
            .where(OrgVendor.org_id == org_id)
            .where(OrgVendor.vendor_name.in_(list(unmatched)))
            .where(func.similarity(KEV.vendor, OrgVendor.vendor_name) > _FUZZY_THRESHOLD)
            .where(
                or_(
                    OrgVendor.product_name == "",
                    func.lower(KEV.product) == func.lower(OrgVendor.product_name),
                )
            )
            .order_by(func.similarity(KEV.vendor, OrgVendor.vendor_name).desc())
        )
        try:
            return list((await self._session.execute(stmt)).all())
        except ProgrammingError:
            # pg_trgm function/operator missing on the DB (SQLSTATE 42883).
            # Degrade gracefully so the endpoint still returns exact + alias
            # matches instead of 500. Connectivity / permission / integrity
            # failures (other SQLAlchemyError subclasses) keep bubbling up.
            logger.warning(
                "vendor fuzzy match failed for org %s — degrading to exact+alias only",
                org_id,
                exc_info=True,
            )
            # Async session is poisoned after a query error — roll back so
            # subsequent queries (e.g. _last_kev_ingest) succeed.
            await self._session.rollback()
            return []

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

        # ── First pass: exact case-insensitive join (confidence = 1.0) ──────
        exact_stmt = (
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
        exact_result = await self._session.execute(exact_stmt)
        exact_rows = exact_result.all()
        exact_vendor_names = {row.vendor_name for row in exact_rows}

        # ── All org vendor names (for determining unmatched set) ─────────────
        all_vendors_result = await self._session.execute(
            select(OrgVendor.vendor_name).where(OrgVendor.org_id == org_id).distinct()
        )
        all_vendor_names = {r[0] for r in all_vendors_result.all()}
        unmatched_vendor_names = all_vendor_names - exact_vendor_names

        # ── Alias pass: resolve known cloud/SaaS names to KEV canonical names ─
        alias_rows = await self._run_alias_pass(org_id, unmatched_vendor_names)
        alias_matched_names = {r.vendor_name for r in alias_rows}
        unmatched_vendor_names -= alias_matched_names

        # ── Second pass: fuzzy match for vendors with no exact match ─────────
        fuzzy_rows = await self._run_fuzzy_pass(org_id, unmatched_vendor_names)
        fuzzy_matched_vendor_names: set[str] = set()
        for row in fuzzy_rows:
            fuzzy_matched_vendor_names.add(row.vendor_name)
            fire_and_forget_normalization_log(
                org_id=org_id,
                data_type="vendor",
                raw_value=row.vendor_name,
                normalized_value=row.kev_vendor,
                method="fuzzy",
                confidence=float(row.score),
            )

        # ── Combine exact + alias + fuzzy results ────────────────────────────
        # Build unified list of dicts for sorting / pagination
        combined: list[dict] = []
        for row in exact_rows:
            combined.append(
                {
                    "vendor_name": row.vendor_name,
                    "org_product": row.org_product,
                    "cve_id": row.cve_id,
                    "kev_product": row.kev_product,
                    "due_date": row.due_date,
                    "description": row.description,
                    "cvss_score": row.cvss_score,
                    "severity": row.severity,
                    "published_date": row.published_date,
                    "match_confidence": 1.0,
                }
            )
        for row in alias_rows:
            combined.append(
                {
                    "vendor_name": row.vendor_name,
                    "org_product": row.org_product,
                    "cve_id": row.cve_id,
                    "kev_product": row.kev_product,
                    "due_date": row.due_date,
                    "description": row.description,
                    "cvss_score": row.cvss_score,
                    "severity": row.severity,
                    "published_date": row.published_date,
                    "match_confidence": 1.0,
                }
            )
        for row in fuzzy_rows:
            combined.append(
                {
                    "vendor_name": row.vendor_name,
                    "org_product": row.org_product,
                    "cve_id": row.cve_id,
                    "kev_product": row.kev_product,
                    "due_date": row.due_date,
                    "description": row.description,
                    "cvss_score": row.cvss_score,
                    "severity": row.severity,
                    "published_date": row.published_date,
                    "match_confidence": float(row.score),
                }
            )

        total_matched = len(combined)

        if total_matched == 0:
            return VendorAlertsResponse(
                total_matched=0,
                severity_breakdown=SeverityBreakdown(),
                items=[],
                page=page,
                page_size=page_size,
                unmatched_vendors=sorted(
                    all_vendor_names - exact_vendor_names - fuzzy_matched_vendor_names
                ),
                reason="no_matches",
                kev_last_ingest_at=await self._last_kev_ingest(),
            )

        # Sort by CVSS desc, then due_date desc (nulls last)
        combined.sort(
            key=lambda r: (
                -(r["cvss_score"] or 0),
                r["due_date"] is None,
                -(r["due_date"].toordinal()) if r["due_date"] else 0,
            )
        )

        # Paginate
        page_start = (page - 1) * page_size
        paginated = combined[page_start : page_start + page_size]

        # Build items for current page
        items: list[VendorAlert] = []
        for r in paginated:
            sev_label = _normalize_severity(r["severity"], r["cvss_score"])
            risk = basic_vuln_risk_score(r["cvss_score"], exploited=True)
            items.append(
                VendorAlert(
                    vendor_name=r["vendor_name"],
                    org_product=r["org_product"],
                    cve_id=r["cve_id"],
                    kev_product=r["kev_product"],
                    due_date=r["due_date"],
                    description=r["description"] or "",
                    cvss_score=r["cvss_score"],
                    severity_label=sev_label,
                    risk_score=risk,
                    published_date=r["published_date"],
                    match_confidence=r["match_confidence"],
                )
            )

        breakdown = _compute_severity_breakdown(combined)

        truly_unmatched = sorted(all_vendor_names - exact_vendor_names - fuzzy_matched_vendor_names)

        return VendorAlertsResponse(
            total_matched=total_matched,
            severity_breakdown=breakdown,
            items=items,
            page=page,
            page_size=page_size,
            unmatched_vendors=truly_unmatched,
            reason=None,
            kev_last_ingest_at=await self._last_kev_ingest(),
        )

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
