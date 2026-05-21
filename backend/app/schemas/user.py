"""Pydantic schemas for user auth."""

from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    id: int  # noqa: A003
    email: str
    is_active: bool
    role: str
    auth_provider: str
    created_at: datetime
    org_id: int | None = None
    org_role: str | None = None
    org_is_demo: bool = False

    model_config = {"from_attributes": True}
