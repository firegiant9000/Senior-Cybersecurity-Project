"""Pydantic schemas for the Findings Engine."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.disclaimer import DisclaimerBlock


class Finding(BaseModel):
    id: str
    # Identity that survives re-ingest: strips count/list inputs that vary
    # run-to-run so finding_statuses joins remain valid across snapshots.
    stable_key: str = ""
    finding_type: str  # threat_exposure | vendor_exposure | data_gap | recommended_action
    severity: str  # critical | high | medium | low | info
    severity_score: float | None = None  # 0-100 numeric score for consistent sorting/filtering
    title: str
    description: str
    evidence: dict
    source: str
    affected_assets: list[str]
    match_confidence: float | None = None  # 1.0 = exact, <1.0 = fuzzy similarity score
    status: str = "open"  # open | done | dismissed (user-set via PATCH)


class FindingsSummary(BaseModel):
    total: int
    by_type: dict[str, int]
    by_severity: dict[str, int]


class FindingsReport(BaseModel):
    org_id: int
    findings: list[Finding]
    summary: FindingsSummary
    generated_at: str
    data_sources_used: list[str]
    assessment_tier: str
    disclaimer_block: DisclaimerBlock | None = None
