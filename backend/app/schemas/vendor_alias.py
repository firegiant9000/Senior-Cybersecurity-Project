"""Pydantic schemas for VendorAlias."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AliasSource = Literal["manual", "nvd", "kev", "community"]


class VendorAliasCreate(BaseModel):
    canonical_vendor: str = Field(..., min_length=1, max_length=255)
    alias: str = Field(..., min_length=1, max_length=255)
    source: AliasSource = "manual"


class VendorAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    canonical_vendor: str
    alias: str
    source: AliasSource
    created_at: datetime
