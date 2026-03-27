"""User ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.organization import Organization


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    firebase_uid: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer", nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(50), default="email", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    org_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="members")
