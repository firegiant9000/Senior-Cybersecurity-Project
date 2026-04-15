"""Pydantic schemas for Findings Snapshot history."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.findings import FindingsSummary


class SnapshotListItem(BaseModel):
    id: int
    generated_at: str
    assessment_tier: str
    summary: FindingsSummary
    data_sources_used: list[str]


class SnapshotListResponse(BaseModel):
    items: list[SnapshotListItem]
    total: int


class SnapshotDetail(BaseModel):
    id: int
    org_id: int
    generated_at: str
    assessment_tier: str
    findings: list[dict]
    summary: FindingsSummary
    data_sources_used: list[str]
