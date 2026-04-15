"""Pydantic schemas for the Findings Engine."""

from __future__ import annotations

from pydantic import BaseModel


class Finding(BaseModel):
    id: str
    finding_type: str  # threat_exposure | vendor_exposure | data_gap | recommended_action
    severity: str  # critical | high | medium | low | info
    severity_score: float | None = None  # 0-100 numeric score for consistent sorting/filtering
    title: str
    description: str
    evidence: dict
    source: str
    affected_assets: list[str]


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
