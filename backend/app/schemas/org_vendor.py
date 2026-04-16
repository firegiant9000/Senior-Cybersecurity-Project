"""Pydantic schemas for OrgVendor endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrgVendorCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    product_name: str = Field("", max_length=255)

    @field_validator("vendor_name", mode="before")
    @classmethod
    def normalize_vendor_name(cls, v: object) -> object:
        if not isinstance(v, str):
            return v  # let Pydantic's type validator produce the proper error
        return " ".join(v.strip().split())

    @field_validator("product_name", mode="before")
    @classmethod
    def normalize_product_name(cls, v: object) -> object:
        if not isinstance(v, str):
            return v if v is not None else ""
        return " ".join(v.strip().split())


class OrgVendorUpdate(BaseModel):
    vendor_name: str | None = Field(None, min_length=1, max_length=255)
    product_name: str | None = Field(None, max_length=255)

    @field_validator("vendor_name", mode="before")
    @classmethod
    def normalize_vendor_name(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        return " ".join(v.strip().split())

    @field_validator("product_name", mode="before")
    @classmethod
    def normalize_product_name(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        return " ".join(v.strip().split())


class OrgVendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    vendor_name: str
    product_name: str
    created_at: datetime
    updated_at: datetime
    matched_kev_count: int = 0


class OrgVendorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrgVendorRead]


class OrgVendorImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class OrgVendorImportPreviewResponse(BaseModel):
    total_rows: int
    would_import: int
    would_skip: int
    errors: list[str]
