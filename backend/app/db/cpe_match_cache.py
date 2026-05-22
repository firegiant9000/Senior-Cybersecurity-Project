"""CpeMatchCache ORM model — vendor+product → CPE URI lookup table.

Pre-staged for the Month 3 CPE-matcher service. Empty in Month 2; the
matcher is developed against this real schema rather than a placeholder.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CpeMatchCache(Base):
    __tablename__ = "cpe_match_cache"
    __table_args__ = (
        UniqueConstraint(
            "vendor_normalized",
            "product_normalized",
            "version_normalized",
            name="uq_cpe_match_cache_vpv",
        ),
        Index("ix_cpe_match_cache_vendor_product", "vendor_normalized", "product_normalized"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    vendor_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    product_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    version_normalized: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cpe_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
