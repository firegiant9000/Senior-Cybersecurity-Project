"""AssetSoftware ORM model — software installed on a discovered asset."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetSoftware(Base):
    __tablename__ = "asset_software"
    __table_args__ = (
        Index("ix_asset_software_org_vendor_product", "org_id", "vendor", "product"),
        Index("ix_asset_software_asset_id", "asset_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized for query speed and org-scoped lookups without join.
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    product: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cpe_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_scan_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="SET NULL"), nullable=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
