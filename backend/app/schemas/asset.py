"""Pydantic schemas for Asset endpoints."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DiscoveredVia = Literal["csv_upload", "m365", "gws", "agent", "manual"]


class AssetCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: str | None = Field(None, max_length=45)
    os_name: str | None = Field(None, max_length=100)
    os_version: str | None = Field(None, max_length=100)
    mac_address: str | None = Field(None, max_length=64)
    discovered_via: DiscoveredVia
    metadata: dict[str, Any] | None = None


class AssetUpdate(BaseModel):
    ip_address: str | None = Field(None, max_length=45)
    os_name: str | None = Field(None, max_length=100)
    os_version: str | None = Field(None, max_length=100)
    mac_address: str | None = Field(None, max_length=64)
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    hostname: str
    ip_address: str | None
    os_name: str | None
    os_version: str | None
    mac_address: str | None
    discovered_via: DiscoveredVia
    first_seen: datetime
    last_seen: datetime
    is_active: bool
    asset_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")
    tags: list[str] | None = None
    created_by_scan_run_id: int | None = None
    created_at: datetime
    updated_at: datetime
    # Convention from Month 1 D2: every response declares its data backing.
    source: str = "csv_upload"


class AssetTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=32)


class AssetListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AssetRead]
