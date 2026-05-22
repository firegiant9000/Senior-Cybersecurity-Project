"""Pydantic schemas for ScanRun endpoints."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ScanSource = Literal["csv_upload", "m365", "gws", "agent"]
ScanStatus = Literal["pending", "running", "succeeded", "failed", "partial"]


class ScanRunCreate(BaseModel):
    source: ScanSource
    triggered_by_user_id: int | None = None
    metadata: dict[str, Any] | None = None


class ScanRunUpdate(BaseModel):
    status: ScanStatus | None = None
    finished_at: datetime | None = None
    asset_count: int | None = Field(None, ge=0)
    software_count: int | None = Field(None, ge=0)
    error_message: str | None = Field(None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ScanRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    source: ScanSource
    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    asset_count: int
    software_count: int
    error_message: str | None
    scan_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")
    triggered_by_user_id: int | None


class ScanRunListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ScanRunRead]
