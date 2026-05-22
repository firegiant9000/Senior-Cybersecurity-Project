"""VendorAlias ORM model — maps display names to a canonical vendor token.

Drives both KEV/NVD matching against uploaded inventory and the existing
vendor watchlist deduplication. Seeded with ~50 common aliases (see
migration 037 and ``scripts/seed_vendor_aliases.py`` future).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VendorAlias(Base):
    __tablename__ = "vendor_aliases"
    __table_args__ = (
        UniqueConstraint("alias", name="uq_vendor_aliases_alias"),
        Index("ix_vendor_aliases_canonical", "canonical_vendor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    canonical_vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
