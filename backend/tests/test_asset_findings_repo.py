"""Repository test: reviewer decisions survive an asset_software re-key.

``commit_inventory`` dedupes software by ``(org, asset, vendor, product,
version)``, so a version change inserts a *new* ``asset_software`` row with a new
surrogate id. If ``replace_for_asset`` keyed status preservation solely on
``asset_software_id`` it would prune the old finding and reopen the CVE as
``open`` — silently discarding a reviewer's ``false_positive`` verdict.

This test proves the carry-forward by stable ``(software_vendor,
software_product, cve_id)`` identity keeps that verdict across the re-key.

Requires the test Postgres.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.asset import Asset
from app.db.asset_finding import AssetFinding
from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal
from app.db.organization import Organization
from app.repositories.asset_findings import FindingInput, SqlAssetFindingRepository


def _input(*, software_id: int) -> FindingInput:
    return FindingInput(
        asset_software_id=software_id,
        cve_id="CVE-2021-44228",
        software_vendor="apache",
        software_product="log4j",
        source="cpe_matcher",
        cpe_uri="cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*",
        cvss_score=10.0,
        epss_score=0.9,
        kev_flag=True,
        severity="critical",
        risk_score=95.0,
        match_confidence="medium",
        remediation_summary="patch it",
    )


@pytest.mark.asyncio
async def test_false_positive_survives_software_rekey():
    async with AsyncSessionLocal() as session:
        org = Organization(name=f"FindingsRepoOrg-{uuid4().hex[:8]}")
        session.add(org)
        await session.flush()

        asset = Asset(org_id=org.id, hostname=f"host-{uuid4().hex[:8]}", discovered_via="csv_upload")
        session.add(asset)
        await session.flush()

        sw_old = AssetSoftware(
            asset_id=asset.id, org_id=org.id, vendor="apache", product="log4j",
            version="2.14.1", source="csv_upload",
        )
        session.add(sw_old)
        await session.flush()

        repo = SqlAssetFindingRepository(session)
        try:
            # Initial matcher run produces the finding.
            await repo.replace_for_asset(asset.id, org.id, [_input(software_id=sw_old.id)])
            await session.commit()

            # Reviewer marks it a false positive.
            finding = (await repo.list_for_asset(asset.id, org.id))[0]
            await repo.update_status(finding.id, org.id, "false_positive")

            # Re-import re-keys the software (version bump → new surrogate id).
            sw_new = AssetSoftware(
                asset_id=asset.id, org_id=org.id, vendor="apache", product="log4j",
                version="2.14.1", source="csv_upload",
            )
            session.add(sw_new)
            await session.flush()
            assert sw_new.id != sw_old.id

            # Recompute against the new software id.
            await repo.replace_for_asset(asset.id, org.id, [_input(software_id=sw_new.id)])
            await session.commit()

            rows = await repo.list_for_asset(asset.id, org.id)
            assert len(rows) == 1, "old finding should be replaced, not duplicated"
            assert rows[0].asset_software_id == sw_new.id
            assert rows[0].status == "false_positive", "reviewer verdict must carry forward"
        finally:
            await session.execute(
                AssetFinding.__table__.delete().where(AssetFinding.org_id == org.id)
            )
            await session.execute(
                AssetSoftware.__table__.delete().where(AssetSoftware.org_id == org.id)
            )
            await session.execute(Asset.__table__.delete().where(Asset.org_id == org.id))
            await session.execute(Organization.__table__.delete().where(Organization.id == org.id))
            await session.commit()
