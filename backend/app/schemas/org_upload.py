"""Pydantic schemas for OrgUpload endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrgUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    uploaded_by: int | None
    original_filename: str
    stored_filename: str
    file_size_bytes: int
    content_type: str
    upload_purpose: str | None
    created_at: datetime


class OrgUploadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrgUploadRead]
