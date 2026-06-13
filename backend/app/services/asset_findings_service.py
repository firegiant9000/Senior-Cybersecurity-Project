"""Compute + persist version-aware findings for an asset (Month 3, Phase 3).

Glues the Phase 2 ``CpeMatcher`` to the per-finding ``risk_scorer`` and the
``asset_findings`` repository: for every piece of software on an asset it runs
the matcher, enriches each CVE match with CVSS/EPSS/KEV context, scores it, and
upserts the result — preserving reviewer-set status across re-runs.

Phase 4's background job and the CSV/M365 import path call
``compute_and_persist_for_asset`` (or ``...for_org``); Phase 3's read endpoint
calls it lazily the first time an asset's findings are requested.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.asset import Asset
from app.db.asset_finding import AssetFinding
from app.db.asset_software import AssetSoftware
from app.db.models import CVE, KEV
from app.repositories.asset_findings import FindingInput, SqlAssetFindingRepository
from app.services.cpe_matcher import CpeMatcher
from app.services.risk_scorer import score_finding

logger = logging.getLogger(__name__)

# Asset tags that mark the host as reachable from the internet (blast-radius
# input to the risk scorer).
_INTERNET_EXPOSED_TAGS = {"internet-facing", "internet-exposed", "public", "dmz"}


def _is_internet_exposed(asset: Asset) -> bool:
    tags = {t.lower() for t in (asset.tags or [])}
    return bool(tags & _INTERNET_EXPOSED_TAGS)


def _days_since(published: datetime | None) -> int | None:
    if published is None:
        return None
    today = datetime.now(UTC).date()
    pub = published.date() if isinstance(published, datetime) else published
    return (today - pub).days


def _remediation_template(*, kev_flag: bool, severity: str | None, product: str) -> str:
    """A short default remediation hint; reviewers can overwrite it later."""
    if kev_flag:
        return (
            f"Listed in CISA KEV — prioritize patching or removing {product} now; "
            "exploited in the wild."
        )
    sev = (severity or "").lower()
    if sev in ("critical", "high"):
        return f"Update {product} to a fixed release; high-severity CVE applies to this version."
    return f"Review {product} and apply the vendor's latest patch."


class AssetFindingsService:
    """Computes and persists version-aware findings for an org's assets."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        matcher: CpeMatcher | None = None,
        repo: SqlAssetFindingRepository | None = None,
    ) -> None:
        self._session = session
        self._matcher = matcher or CpeMatcher(session)
        self._repo = repo or SqlAssetFindingRepository(session)

    async def compute_and_persist_for_asset(self, asset_id: int, org_id: int) -> list[AssetFinding]:
        """Run the matcher over one asset's software and persist the findings.

        Commits the transaction. Returns the persisted findings (riskiest
        first). An asset with no software yields an empty, pruned result.
        """
        asset = (
            await self._session.execute(
                select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
            )
        ).scalar_one_or_none()
        if asset is None:
            return []

        software = list(
            (
                await self._session.execute(
                    select(AssetSoftware).where(
                        AssetSoftware.asset_id == asset_id,
                        AssetSoftware.org_id == org_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        inputs = await self._build_findings(asset, software)
        persisted = await self._repo.replace_for_asset(asset_id, org_id, inputs)
        await self._session.commit()
        return persisted

    async def compute_and_persist_for_org(self, org_id: int) -> int:
        """Recompute findings for every asset in an org. Returns asset count."""
        asset_ids = list(
            (await self._session.execute(select(Asset.id).where(Asset.org_id == org_id)))
            .scalars()
            .all()
        )
        for asset_id in asset_ids:
            await self.compute_and_persist_for_asset(asset_id, org_id)
        return len(asset_ids)

    async def _build_findings(
        self, asset: Asset, software: list[AssetSoftware]
    ) -> list[FindingInput]:
        """Match every software row, enrich + score each CVE, dedupe by pairing."""
        if not software:
            return []

        internet_exposed = _is_internet_exposed(asset)

        # (asset_software_id, cve_id) → FindingInput, keeping the highest score
        # if the same CVE surfaces from more than one CPE criterion.
        chosen: dict[tuple[int, str], FindingInput] = {}

        for sw in software:
            matches = await self._matcher.match(
                vendor=sw.vendor,
                product=sw.product,
                version=sw.version,
                cpe_uri=sw.cpe_uri,
                write_back=True,
            )
            if not matches:
                continue

            cve_meta = await self._load_cve_meta({m.cve_id for m in matches})

            for match in matches:
                meta = cve_meta.get(match.cve_id.upper())
                cvss = meta["cvss_score"] if meta else None
                epss = meta["epss_score"] if meta else None
                severity = meta["severity"] if meta else None
                kev_flag = bool(meta["kev_flag"]) if meta else False
                published = meta["published_date"] if meta else None

                risk = score_finding(
                    confidence=match.confidence,
                    cvss_score=cvss,
                    epss_score=epss,
                    kev_flag=kev_flag,
                    asset_criticality=asset.asset_criticality,
                    internet_exposed=internet_exposed,
                    days_since_disclosure=_days_since(published),
                )

                candidate = FindingInput(
                    asset_software_id=sw.id,
                    cve_id=match.cve_id.upper(),
                    source="cpe_matcher",
                    cpe_uri=match.cpe_uri[:500],
                    cvss_score=cvss,
                    epss_score=epss,
                    kev_flag=kev_flag,
                    severity=severity,
                    risk_score=risk.score,
                    match_confidence=match.confidence,
                    remediation_summary=_remediation_template(
                        kev_flag=kev_flag, severity=severity, product=sw.product
                    ),
                )
                key = (sw.id, candidate.cve_id)
                current = chosen.get(key)
                if current is None or (candidate.risk_score or 0.0) > (current.risk_score or 0.0):
                    chosen[key] = candidate

        return list(chosen.values())

    async def _load_cve_meta(self, cve_ids: set[str]) -> dict[str, dict]:
        """Bulk-load CVSS/EPSS/severity/published + KEV flag for the given CVEs."""
        if not cve_ids:
            return {}
        upper_ids = {c.upper() for c in cve_ids}

        cve_rows = (
            await self._session.execute(
                select(
                    CVE.cve_id,
                    CVE.cvss_score,
                    CVE.epss_score,
                    CVE.severity,
                    CVE.published_date,
                ).where(CVE.cve_id.in_(upper_ids))
            )
        ).all()

        kev_ids = {
            str(row[0]).upper()
            for row in (
                await self._session.execute(select(KEV.cve_id).where(KEV.cve_id.in_(upper_ids)))
            ).all()
        }

        meta: dict[str, dict] = {}
        for cve_id, cvss, epss, severity, published in cve_rows:
            key = str(cve_id).upper()
            meta[key] = {
                "cvss_score": float(cvss) if cvss is not None else None,
                "epss_score": float(epss) if epss is not None else None,
                "severity": severity,
                "published_date": published,
                "kev_flag": key in kev_ids,
            }
        return meta
