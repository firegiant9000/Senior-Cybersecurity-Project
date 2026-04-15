"""Pydantic schemas for Organization endpoints."""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import (
    INDUSTRY_TO_IC3_SECTOR,
    EmployeeRange,
    IndustryLabel,
    RevenueRange,
)


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry_label: IndustryLabel
    primary_state: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    employee_range: EmployeeRange
    revenue_range: RevenueRange | None = None
    ic3_sector: str = Field("", json_schema_extra={"hidden": True})
    security_controls: dict[str, str] | None = None
    cloud_providers: list[str] | None = None
    compliance_frameworks: list[str] | None = None
    data_types: list[str] | None = None
    device_count_range: str | None = None
    incident_history: str | None = None

    # Fields to exclude from the OpenAPI request schema.
    _server_derived: ClassVar[set[str]] = {"ic3_sector"}

    @model_validator(mode="after")
    def _derive_ic3_sector(self):
        """Auto-derive ic3_sector from industry_label."""
        self.ic3_sector = str(INDUSTRY_TO_IC3_SECTOR[self.industry_label])
        return self

    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        for field in cls._server_derived:
            schema.get("properties", {}).pop(field, None)
            if field in schema.get("required", []):
                schema["required"].remove(field)
        return schema


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    industry_label: IndustryLabel | None = None
    primary_state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    employee_range: EmployeeRange | None = None
    revenue_range: RevenueRange | None = None
    logo_url: str | None = Field(None, max_length=500)
    primary_domain: str | None = Field(None, max_length=255)
    ic3_sector: str | None = Field(None, json_schema_extra={"hidden": True})
    security_controls: dict[str, str] | None = None
    cloud_providers: list[str] | None = None
    compliance_frameworks: list[str] | None = None
    data_types: list[str] | None = None
    device_count_range: str | None = None
    incident_history: str | None = None

    _server_derived: ClassVar[set[str]] = {"ic3_sector"}

    @model_validator(mode="after")
    def _derive_ic3_sector(self):
        """Re-derive ic3_sector when industry_label changes."""
        if self.industry_label is not None:
            self.ic3_sector = str(INDUSTRY_TO_IC3_SECTOR[self.industry_label])
        return self

    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        for field in cls._server_derived:
            schema.get("properties", {}).pop(field, None)
        return schema


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    name: str
    industry_label: str
    ic3_sector: str
    primary_state: str
    employee_range: str
    revenue_range: str | None = None
    logo_url: str | None = None
    primary_domain: str | None = None
    security_controls: dict[str, str] | None = None
    cloud_providers: list[str] | None = None
    compliance_frameworks: list[str] | None = None
    data_types: list[str] | None = None
    device_count_range: str | None = None
    incident_history: str | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrganizationRead]
