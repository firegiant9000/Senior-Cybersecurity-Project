"""Findings Snapshot ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FindingsSnapshot(Base):
    __tablename__ = "findings_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    findings: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    assessment_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    data_sources_used: Mapped[list] = mapped_column(JSON, nullable=False)
