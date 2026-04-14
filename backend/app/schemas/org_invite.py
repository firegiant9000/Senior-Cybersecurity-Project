"""Pydantic schemas for organization invite and member management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.enums import OrgRole


class InviteCreate(BaseModel):
    email: EmailStr
    org_role: OrgRole = OrgRole.MEMBER


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    invited_email: str
    org_role: str
    status: str
    invited_by: int | None = None
    expires_at: datetime
    created_at: datetime


class InviteListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[InviteRead]


class InviteTokenRead(BaseModel):
    """Public-facing invite info returned when looking up a token."""

    invite_token: str
    org_name: str
    org_role: str
    invited_email: str
    expires_at: datetime


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    email: str
    org_role: str | None
    is_active: bool
    created_at: datetime


class MemberListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MemberRead]


class MemberUpdate(BaseModel):
    org_role: OrgRole = Field(..., description="New organization role for the member")
