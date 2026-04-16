"""Pydantic schemas for OrgDomain endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrgDomainCreate(BaseModel):
    domain_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$",
    )

    @field_validator("domain_name", mode="before")
    @classmethod
    def normalize_domain_name(cls, v: str) -> str:
        return v.strip().lower().rstrip(".")


class OrgDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    domain_name: str
    is_verified: bool
    added_by: int | None
    created_at: datetime
    updated_at: datetime


class OrgDomainListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrgDomainRead]
