"""Asset ORM model — inventory device discovered for an organization."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        # NULL-safe uniqueness on (org_id, hostname, mac_address). Defined in the
        # migration via COALESCE; this unique index lives at the DB level rather
        # than as a SQLAlchemy UniqueConstraint because of the COALESCE.
        Index(
            "ix_assets_org_hostname",
            "org_id",
            "hostname",
        ),
        Index("ix_assets_org_is_active", "org_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discovered_via: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    # Drives the per-finding risk scorer (low|normal|high|critical). Defaults
    # to ``normal`` so existing assets score neutrally until classified.
    asset_criticality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'normal'"), default="normal"
    )
    asset_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    # Latest read-only host observations from the agent scanner (Month 4 Phase 3).
    # Replace-on-scan snapshots, not history: ``services`` is a list of
    # {name, state}; ``listening_ports`` a list of {port, protocol, process}.
    # Only the agent path writes these, and only when a scan actually reports the
    # field, so a CSV/M365 import never clobbers agent-collected data.
    services: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    listening_ports: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_by_scan_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
