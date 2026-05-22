"""ScanRun ORM model — one inventory ingest event (CSV upload, M365 sync, etc.)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScanRun(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (
        Index("ix_scan_runs_org_started", "org_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    software_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    scan_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
