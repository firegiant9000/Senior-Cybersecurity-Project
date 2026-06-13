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
    "software_vendor",
    "software_product",
)

# Reviewer-owned fields carried forward when a finding is re-associated to a
# new ``asset_software_id`` (e.g. after a re-import churns the surrogate key).
_REVIEWER_FIELDS = ("status", "false_positive_reported_by", "remediation_summary")


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
    # Stable software identity used to re-associate reviewer state when the
    # surrogate ``asset_software_id`` changes across re-imports.
    software_vendor: str | None = None
    software_product: str | None = None
    # Templated default applied only on first insert; never overwrites a
    # reviewer-edited summary on recompute.
    remediation_summary: str | None = None


def _identity(vendor: str | None, product: str | None, cve_id: str) -> tuple[str, str, str]:
    """Stable, version-agnostic finding identity for status preservation."""
    return ((vendor or "").lower(), (product or "").lower(), cve_id)


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

    async def replace_for_asset(  # noqa: C901
        self,
        asset_id: int,
        org_id: int,
        findings: list[FindingInput],
    ) -> list[AssetFinding]:
        """Upsert ``findings`` for an asset and prune stale rows.

        Existing rows matched by ``(asset_software_id, cve_id)`` are updated in
        place — preserving reviewer state. New pairings are inserted; when the
        surrogate key missed but a *stale* row shares the same stable identity
        ``(software_vendor, software_product, cve_id)`` (i.e. a re-import re-keyed
        the software), the reviewer's ``status`` / false-positive report /
        remediation note are carried forward onto the new row so a closed
        finding is never silently reopened. Pairings absent from ``findings`` are
        deleted. Does not commit; the caller owns the transaction boundary.
        """
        existing = await self.list_for_asset(asset_id, org_id)
        by_key = {(r.asset_software_id, r.cve_id): r for r in existing}
        incoming_keys: set[tuple[int, str]] = set()

        # Stale rows (not matched by surrogate key) indexed by stable identity,
        # so an insert can inherit a reviewer decision from the row it replaces.
        matched_ids: set[int] = set()
        stale_by_identity: dict[tuple[str, str, str], AssetFinding] = {}

        for item in findings:
            key = (item.asset_software_id, item.cve_id)
            incoming_keys.add(key)
            row = by_key.get(key)
            if row is not None:
                for field in _COMPUTED_FIELDS:
                    setattr(row, field, getattr(item, field))
                matched_ids.add(row.id)

        # Anything not updated above is a candidate to be pruned — but first make
        # its reviewer state available for re-association by stable identity.
        for r in existing:
            if r.id not in matched_ids:
                stale_by_identity[_identity(r.software_vendor, r.software_product, r.cve_id)] = r

        for item in findings:
            if (item.asset_software_id, item.cve_id) in by_key:
                continue  # already updated in place
            new_row = AssetFinding(
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
                software_vendor=item.software_vendor,
                software_product=item.software_product,
                remediation_summary=item.remediation_summary,
            )
            prior = stale_by_identity.get(
                _identity(item.software_vendor, item.software_product, item.cve_id)
            )
            if prior is not None:
                for field in _REVIEWER_FIELDS:
                    setattr(new_row, field, getattr(prior, field))
            self._session.add(new_row)

        # Prune every row not updated in place. A stale row whose reviewer state
        # was carried onto a freshly-inserted replacement is deleted here — its
        # decision now lives on the new row (which has a different surrogate key,
        # so no unique-constraint conflict).
        stale = [r.id for r in existing if r.id not in matched_ids]
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
