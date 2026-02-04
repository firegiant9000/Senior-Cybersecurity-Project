"""IngestRun Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestRunBase(BaseModel):
    """Base IngestRun schema."""

    source: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="pending", max_length=50)
    records_ingested: int = Field(default=0, ge=0)


class IngestRunCreate(IngestRunBase):
    """Schema for creating an IngestRun."""

    pass


class IngestRunUpdate(BaseModel):
    """Schema for updating an IngestRun."""

    status: str | None = Field(None, max_length=50)
    finished_at: datetime | None = None
    records_ingested: int | None = Field(None, ge=0)
    error_message: str | None = None


class IngestRunResponse(IngestRunBase):
    """Schema for IngestRun response."""

    id: UUID
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None

    class Config:
        """Pydantic config."""

        from_attributes = True
