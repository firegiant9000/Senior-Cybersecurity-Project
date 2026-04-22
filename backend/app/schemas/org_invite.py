"""Pydantic schemas for organization invite and member management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.enums import OrgRole


class InviteCreate(BaseModel):
    email: EmailStr
    role: OrgRole = Field(default=OrgRole.MEMBER, validation_alias="org_role")


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: A003
    org_id: int
    email: str
    role: str
    status: str
    inviter_id: int | None = None
    expires_at: datetime
    created_at: datetime


class InviteListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[InviteRead]


class InviteTokenRead(BaseModel):
    """Public-facing invite info returned when looking up a token."""

    token: str
    org_name: str
    role: str
    email: str
    expires_at: datetime


class MemberRead(BaseModel):
    user_id: int
    email: str
    role: str
    status: str
    is_active: bool
    created_at: datetime


class MemberListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MemberRead]


class MemberUpdate(BaseModel):
    role: OrgRole = Field(
        ...,
        validation_alias="org_role",
        description="New organization role for the member",
    )
