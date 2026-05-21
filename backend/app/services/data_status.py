"""Single source of truth for per-dataset source-status labels.

Each dashboard widget / dataset reports one of four backings:

- ``real``    — live data refreshed from the upstream source on a known cadence
- ``static``  — a frozen, manually-curated snapshot (e.g. one-time CSV import)
- ``mocked``  — placeholder values, not real data
- ``pending`` — feature is wired up but no data has been ingested yet
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel  # type: ignore[import-not-found]

SourceStatus = Literal["real", "static", "mocked", "pending"]


class DatasetStatus(BaseModel):
    """Status entry for a single dataset / dashboard widget."""

    key: str
    label: str
    status: SourceStatus
    source: str
    notes: str | None = None


class DataStatusResponse(BaseModel):
    """Response model for ``GET /api/v1/data-status``."""

    items: list[DatasetStatus]


# Order matches the dashboard surfaces in `docs/DATA_SOURCE_STATUS.md`. Keep in
# sync — the doc cross-references this registry.
_REGISTRY: list[DatasetStatus] = [
    DatasetStatus(
        key="nvd_cves",
        label="NVD CVE catalog",
        status="real",
        source="NIST National Vulnerability Database (NVD) — refreshed via scheduled ingest",
    ),
    DatasetStatus(
        key="kev",
        label="CISA Known Exploited Vulnerabilities",
        status="real",
        source="CISA KEV catalog — refreshed via scheduled ingest",
    ),
    DatasetStatus(
        key="ic3_incidents",
        label="IC3 incidents (national)",
        status="static",
        source="FBI IC3 2023 annual report (static summary)",
        notes="Annual snapshot; updated when the next FBI IC3 report is released.",
    ),
    DatasetStatus(
        key="ic3_geographic",
        label="IC3 geographic heatmap",
        status="static",
        source="FBI IC3 2023 annual report (static summary)",
    ),
    DatasetStatus(
        key="ic3_sector_attack_matrix",
        label="IC3 sector × attack matrix",
        status="static",
        source="FBI IC3 2023 annual report (static summary)",
    ),
    DatasetStatus(
        key="ic3_temporal_trends",
        label="IC3 temporal trends",
        status="static",
        source="FBI IC3 annual reports (static summary, multi-year)",
    ),
    DatasetStatus(
        key="bea_economics",
        label="BEA economic indicators",
        status="real",
        source="U.S. Bureau of Economic Analysis (BEA) API",
    ),
    DatasetStatus(
        key="executive_summary",
        label="Executive summary",
        status="real",
        source="Derived from org profile + NVD/KEV/IC3 aggregates",
    ),
    DatasetStatus(
        key="risk_score",
        label="Composite CVE risk score",
        status="real",
        source="Derived from CVSS + KEV signals",
    ),
    DatasetStatus(
        key="vendor_alerts",
        label="Vendor alerts",
        status="real",
        source="KEV matches against the org's declared vendor stack",
    ),
    DatasetStatus(
        key="loss_projection",
        label="Projected annual loss",
        status="static",
        source="Statistical model over IC3 sector benchmarks",
        notes="Inputs are static IC3 figures; recompute is live but underlying base rates are static.",
    ),
    DatasetStatus(
        key="ai_summary",
        label="AI summary",
        status="real",
        source="LLM-generated summary over current dashboard signals",
    ),
    DatasetStatus(
        key="domain_checks",
        label="Domain checks (HIBP / Shodan / OTX)",
        status="pending",
        source="Third-party APIs (keys present, route not yet shipped)",
        notes="Lands in Month 1 Phase E (#110).",
    ),
    DatasetStatus(
        key="anomalies_ic3",
        label="IC3 anomaly detection",
        status="static",
        source="Statistical z-score over IC3 static dataset",
    ),
    DatasetStatus(
        key="anomalies_vendors",
        label="Vendor anomaly detection",
        status="real",
        source="Derived from live KEV / NVD signals",
    ),
]


_BY_KEY: dict[str, DatasetStatus] = {item.key: item for item in _REGISTRY}


def list_data_status() -> list[DatasetStatus]:
    """Return the full registry of dataset statuses."""
    return list(_REGISTRY)


def get_data_status(key: str) -> DatasetStatus | None:
    """Return the status entry for a specific dataset key, or None if unknown."""
    return _BY_KEY.get(key)


# Conventional label reused inline by IC3 routes (D2). Kept here so frontend
# strings, IC3 routes, and the registry never drift.
IC3_STATIC_SOURCE_LABEL = "FBI IC3 2023 annual report (static summary)"
