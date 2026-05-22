"""Pydantic schemas for AssetSoftware endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SoftwareSource = Literal["csv_upload", "m365", "gws", "agent", "manual"]


class AssetSoftwareCreate(BaseModel):
    vendor: str = Field(..., min_length=1, max_length=255)
    product: str = Field(..., min_length=1, max_length=255)
    version: str | None = Field(None, max_length=100)
    cpe_uri: str | None = Field(None, max_length=500)
    source: SoftwareSource


class AssetSoftwareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    asset_id: int
    org_id: int
    vendor: str
    product: str
    version: str | None
    cpe_uri: str | None
    source: SoftwareSource
    first_seen: datetime
    last_seen: datetime
    created_at: datetime
