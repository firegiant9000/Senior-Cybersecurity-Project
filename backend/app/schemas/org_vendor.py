"""Pydantic schemas for OrgVendor endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrgVendorCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    product_name: str = Field("", max_length=255)


class OrgVendorUpdate(BaseModel):
    vendor_name: str | None = Field(None, min_length=1, max_length=255)
    product_name: str | None = Field(None, max_length=255)


class OrgVendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    vendor_name: str
    product_name: str
    created_at: datetime
    updated_at: datetime


class OrgVendorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrgVendorRead]


class OrgVendorImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
