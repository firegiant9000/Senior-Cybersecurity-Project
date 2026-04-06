"""Pydantic schemas for TechnologyVendor (global catalog) endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TechnologyVendorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field("", max_length=255)
    category: str = Field("", max_length=255)


class TechnologyVendorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    version: str | None = Field(None, max_length=255)
    category: str | None = Field(None, max_length=255)


class TechnologyVendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    name: str
    version: str
    category: str
    created_at: datetime
    updated_at: datetime
