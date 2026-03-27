"""Pydantic schemas for Organization endpoints."""

from datetime import datetime

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
    revenue_range: RevenueRange

    @model_validator(mode="after")
    def _derive_ic3_sector(self):
        """Auto-derive ic3_sector from industry_label."""
        self.ic3_sector = str(INDUSTRY_TO_IC3_SECTOR[self.industry_label])
        return self

    # Populated by the validator; not required in the request body.
    ic3_sector: str = ""


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    industry_label: IndustryLabel | None = None
    primary_state: str | None = Field(
        None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$"
    )
    employee_range: EmployeeRange | None = None
    revenue_range: RevenueRange | None = None

    @model_validator(mode="after")
    def _derive_ic3_sector(self):
        """Re-derive ic3_sector when industry_label changes."""
        if self.industry_label is not None:
            self.ic3_sector = str(INDUSTRY_TO_IC3_SECTOR[self.industry_label])
        return self

    ic3_sector: str | None = None


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry_label: str
    ic3_sector: str
    primary_state: str
    employee_range: str
    revenue_range: str
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrganizationRead]
