"""Integration test: CpeMatcher driven through real SQL, end-to-end.

The Phase 5 regression harness (``tests/regression/matcher_known_good.py``)
feeds the matcher a hand-curated in-memory criteria catalog via a fake session,
so it validates the version comparator but bypasses the parts most likely to
fail in production: the ``cve_cpe_match`` lookup (``_fetch_criteria``), the
empty-table state, and the ``cpe_match_cache`` write-back.

This test closes that gap. It persists CPE criteria with the real NVD parser
(``persist_cpe_configurations``) into a real ``cve_cpe_match`` table and then
drives ``CpeMatcher.match`` through the real ``_fetch_criteria`` SQL — no mocks.

Requires the test Postgres (same as the other DB-backed suites).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.cpe_match_cache import CpeMatchCache
from app.db.cve_cpe_match import CveCpeMatch
from app.db.engine import AsyncSessionLocal
from app.ingestors.nvd_cpe import persist_cpe_configurations
from app.services.cpe_matcher import CpeMatcher

# A realistic NVD API-2.0 payload: Apache log4j affected from 2.0 up to (but not
# including) the 2.15.0 fix — the Log4Shell version boundary.
_LOG4SHELL_PAYLOAD = {
    "configurations": [
        {
            "nodes": [
                {
                    "operator": "OR",
                    "cpeMatch": [
                        {
                            "vulnerable": True,
                            "criteria": "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                            "versionStartIncluding": "2.0",
                            "versionEndExcluding": "2.15.0",
                        }
                    ],
                }
            ]
        }
    ]
}


@pytest.mark.asyncio
async def test_matcher_real_sql_roundtrip():
    """Persist criteria via the parser, then match through real _fetch_criteria."""
    cve_id = f"CVE-2021-{uuid4().int % 100000:05d}"
    async with AsyncSessionLocal() as session:
        try:
            persisted = await persist_cpe_configurations(
                session, cve_id=cve_id, cve=_LOG4SHELL_PAYLOAD
            )
            await session.commit()
            assert persisted == 1  # parser preserved the single criterion

            matcher = CpeMatcher(session)

            # 1) Empty-table state for unknown software: the realistic
            #    not-yet-backfilled case must yield no findings, not an error.
            none_matches = await matcher.match(
                vendor="nonexistent", product=f"ghost_{uuid4().hex[:8]}", version="1.0"
            )
            assert none_matches == []

            # 2) In-range version → a real finding via the DB lookup. A
            #    range match is "medium" (name normalized, version-in-range).
            hits = await matcher.match(
                vendor="apache", product="log4j", version="2.14.1", write_back=True
            )
            assert [m.cve_id for m in hits] == [cve_id]
            assert hits[0].confidence == "medium"

            # 3) Patched version is outside the range → pruned, no finding.
            patched = await matcher.match(vendor="apache", product="log4j", version="2.16.0")
            assert patched == []

            # 4) write_back persisted the resolved CPE to cpe_match_cache.
            await session.commit()
            cached = (
                await session.execute(
                    CpeMatchCache.__table__.select().where(
                        CpeMatchCache.vendor_normalized == "apache",
                        CpeMatchCache.product_normalized == "log4j",
                        CpeMatchCache.version_normalized == "2.14.1",
                    )
                )
            ).first()
            assert cached is not None
        finally:
            await session.execute(
                CveCpeMatch.__table__.delete().where(CveCpeMatch.cve_id == cve_id)
            )
            await session.execute(
                CpeMatchCache.__table__.delete().where(
                    CpeMatchCache.vendor_normalized == "apache",
                    CpeMatchCache.product_normalized == "log4j",
                    CpeMatchCache.version_normalized == "2.14.1",
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_wildcard_cpe_does_not_yield_high_confidence():
    """A version-agnostic (wildcard) criterion must not produce a 'high' match.

    Guards the assign_confidence fix: two wildcard-version CPEs share a core but
    only agree on vendor/product, so granting 'high' would be a version-blind
    false positive.
    """
    cve_id = f"CVE-2020-{uuid4().int % 100000:05d}"
    payload = {
        "configurations": [
            {
                "nodes": [
                    {
                        "operator": "OR",
                        "cpeMatch": [
                            {
                                "vulnerable": True,
                                "criteria": "cpe:2.3:a:examplecorp:widget:*:*:*:*:*:*:*:*",
                            }
                        ],
                    }
                ]
            }
        ]
    }
    async with AsyncSessionLocal() as session:
        try:
            await persist_cpe_configurations(session, cve_id=cve_id, cve=payload)
            await session.commit()
            matcher = CpeMatcher(session)
            hits = await matcher.match(
                vendor="examplecorp",
                product="widget",
                version="1.2.3",
                cpe_uri="cpe:2.3:a:examplecorp:widget:*:*:*:*:*:*:*:*",
                write_back=False,
            )
            assert [m.cve_id for m in hits] == [cve_id]
            assert hits[0].confidence != "high"
        finally:
            await session.execute(
                CveCpeMatch.__table__.delete().where(CveCpeMatch.cve_id == cve_id)
            )
            await session.commit()
