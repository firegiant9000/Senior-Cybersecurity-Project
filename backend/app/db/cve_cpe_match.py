"""CveCpeMatch ORM model — per-CVE CPE criteria with affected version ranges.

This is the *CVE → affected-version-ranges* source of truth, populated from NVD
CPE configurations during ingest (see ``app/ingestors/nvd_cpe.py``). It is
distinct from ``cpe_match_cache`` (a normalized vendor/product/version → CPE-URI
lookup); the Month 3 matcher reads both. ``cve_id`` is an indexed string rather
than a hard FK so CPE rows can be persisted independently of CVE-row ordering.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CveCpeMatch(Base):
    __tablename__ = "cve_cpe_match"
    __table_args__ = (
        Index("ix_cve_cpe_match_cve_id", "cve_id"),
        Index("ix_cve_cpe_match_vendor_product", "vendor", "product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    cve_id: Mapped[str] = mapped_column(String(50), nullable=False)
    cpe_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version_start_including: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_start_excluding: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_end_including: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_end_excluding: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vulnerable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
