"""Organization ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, String, func
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
    revenue_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_controls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cloud_providers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    compliance_frameworks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    data_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    device_count_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    incident_history: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # When true, this org reads from curated demo fixtures instead of the live
    # database. The single canonical public-demo org (used by unauthenticated
    # routes) is seeded with name "Public Demo" by scripts/seed_demo_org.py.
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    members: Mapped[list[User]] = relationship(back_populates="organization")
