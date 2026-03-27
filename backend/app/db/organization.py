"""Organization ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.user import User


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry_label: Mapped[str] = mapped_column(String(100), nullable=False)
    ic3_sector: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_state: Mapped[str] = mapped_column(String(2), nullable=False)
    employee_range: Mapped[str] = mapped_column(String(50), nullable=False)
    revenue_range: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    members: Mapped[list["User"]] = relationship(back_populates="organization")
