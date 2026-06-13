"""Repository for AssetFinding rows — persisted version-aware CVE matches.

All queries are org-scoped. ``replace_for_asset`` is the write path the matcher
service uses: it upserts the freshly computed findings and prunes the ones that
no longer match, while preserving the reviewer-set ``status`` /
``false_positive_reported_by`` / ``remediation_summary`` across recomputes so a
re-run of the matcher never silently reopens a finding someone closed.
"""

# pylint: disable=too-few-public-methods

import logging
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.asset_finding import AssetFinding
from app.db.engine import get_session

logger = logging.getLogger(__name__)

# Status workflow for a finding. ``open`` is the default; the rest are
# reviewer-driven transitions.
ALLOWED_FINDING_STATUSES = {
    "open",
    "accepted_risk",
    "false_positive",
    "in_progress",
    "fixed",
}

# Fields the matcher recomputes; everything else (status + reviewer fields) is
# preserved on re-run.
_COMPUTED_FIELDS = (
    "source",
    "cpe_uri",
    "cvss_score",
    "epss_score",
    "kev_flag",
    "severity",
    "risk_score",
    "match_confidence",
)


@dataclass(frozen=True)
class FindingInput:
    """One computed finding the matcher hands to ``replace_for_asset``."""

    asset_software_id: int
    cve_id: str
    source: str
    cpe_uri: str | None
    cvss_score: float | None
    epss_score: float | None
    kev_flag: bool
    severity: str | None
    risk_score: float | None
    match_confidence: str
    # Templated default applied only on first insert; never overwrites a
    # reviewer-edited summary on recompute.
    remediation_summary: str | None = None


class SqlAssetFindingRepository:
    """Reads and writes ``asset_findings`` scoped to a single org."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_asset(self, asset_id: int, org_id: int) -> list[AssetFinding]:
        """Return all findings for an asset, riskiest first."""
        result = await self._session.execute(
            select(AssetFinding)
            .where(AssetFinding.asset_id == asset_id, AssetFinding.org_id == org_id)
            .order_by(AssetFinding.risk_score.desc().nullslast(), AssetFinding.cve_id)
        )
        return list(result.scalars().all())

    async def count_for_asset(self, asset_id: int, org_id: int) -> int:
        result = await self._session.execute(
            select(func.count(AssetFinding.id)).where(
                AssetFinding.asset_id == asset_id, AssetFinding.org_id == org_id
            )
        )
        return int(result.scalar_one())

    async def get(self, finding_id: int, org_id: int) -> AssetFinding | None:
        result = await self._session.execute(
            select(AssetFinding).where(AssetFinding.id == finding_id, AssetFinding.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        finding_id: int,
        org_id: int,
        status: str,
        *,
        reported_by: int | None = None,
        remediation_summary: str | None = None,
    ) -> AssetFinding | None:
        """Move a finding through the status workflow.

        ``reported_by`` is stamped onto ``false_positive_reported_by`` only when
        the new status is ``false_positive`` (and cleared otherwise), so the
        column always reflects the current verdict rather than a stale report.
        """
        if status not in ALLOWED_FINDING_STATUSES:
            raise ValueError(f"invalid status: {status}")
        row = await self.get(finding_id, org_id)
        if row is None:
            return None
        row.status = status
        row.false_positive_reported_by = reported_by if status == "false_positive" else None
        if remediation_summary is not None:
            row.remediation_summary = remediation_summary
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def replace_for_asset(
        self,
        asset_id: int,
        org_id: int,
        findings: list[FindingInput],
    ) -> list[AssetFinding]:
        """Upsert ``findings`` for an asset and prune stale rows.

        Existing rows matched by ``(asset_software_id, cve_id)`` are updated
        in place — preserving reviewer state — while new pairings are inserted
        and pairings absent from ``findings`` are deleted. Does not commit; the
        caller owns the transaction boundary.
        """
        existing = await self.list_for_asset(asset_id, org_id)
        by_key = {(r.asset_software_id, r.cve_id): r for r in existing}
        incoming_keys: set[tuple[int, str]] = set()

        for item in findings:
            key = (item.asset_software_id, item.cve_id)
            incoming_keys.add(key)
            row = by_key.get(key)
            if row is None:
                self._session.add(
                    AssetFinding(
                        org_id=org_id,
                        asset_id=asset_id,
                        asset_software_id=item.asset_software_id,
                        cve_id=item.cve_id,
                        source=item.source,
                        cpe_uri=item.cpe_uri,
                        cvss_score=item.cvss_score,
                        epss_score=item.epss_score,
                        kev_flag=item.kev_flag,
                        severity=item.severity,
                        risk_score=item.risk_score,
                        match_confidence=item.match_confidence,
                        remediation_summary=item.remediation_summary,
                    )
                )
            else:
                for field in _COMPUTED_FIELDS:
                    setattr(row, field, getattr(item, field))

        stale = [r.id for k, r in by_key.items() if k not in incoming_keys]
        if stale:
            await self._session.execute(
                delete(AssetFinding).where(
                    AssetFinding.org_id == org_id, AssetFinding.id.in_(stale)
                )
            )

        await self._session.flush()
        return await self.list_for_asset(asset_id, org_id)


def get_asset_finding_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAssetFindingRepository:
    """FastAPI dependency factory."""
    return SqlAssetFindingRepository(session)
