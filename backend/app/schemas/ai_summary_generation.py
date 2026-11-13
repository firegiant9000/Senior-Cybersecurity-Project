"""Pydantic schemas for AI Summary Generation history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.core.errors import public_error


class AISummaryGenerationListItem(BaseModel):
    id: int
    org_id: int
    generated_at: datetime
    model_name: str
    source: str
    status: str
    error_message: str | None
    output_text: str | None
    output_format: str
    latency_ms: int | None
    findings_snapshot_id: int | None

    model_config = {"from_attributes": True}

    @field_validator("error_message")
    @classmethod
    def _redact_error_message(cls, v: str | None) -> str | None:
        return public_error(v)


class AISummaryGenerationDetail(AISummaryGenerationListItem):
    prompt_inputs: dict[str, Any]
    rendered_prompt: str | None
    output_meta: dict[str, Any] | None


class AISummaryGenerationListResponse(BaseModel):
    items: list[AISummaryGenerationListItem]
    total: int
    limit: int
    offset: int
