"""AssetFinding ORM model — a persisted version-aware CVE match on an asset.

Month 3, Phase 3. Replaces the in-memory, literal vendor+product matching that
``GET /assets/{id}/findings`` recomputed on every request. Each row is one
``asset_software`` ↔ CVE pairing produced by the Phase 2 ``CpeMatcher``, carrying
its ``match_confidence`` tier, a per-finding ``risk_score``/``severity``, and a
remediation ``status`` the reviewer can move through. Distinct from
``finding_statuses`` (keyed by an opaque ``stable_key`` for the org-level
findings report); this table is keyed by concrete asset/software/CVE rows.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetFinding(Base):
    __tablename__ = "asset_findings"
    __table_args__ = (
        # Re-running the matcher upserts on this identity rather than
        # duplicating rows.
        UniqueConstraint("asset_software_id", "cve_id", name="uq_asset_finding_software_cve"),
        Index("ix_asset_findings_org_asset", "org_id", "asset_id"),
        Index("ix_asset_findings_org_status", "org_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    asset_software_id: Mapped[int] = mapped_column(
        ForeignKey("asset_software.id", ondelete="CASCADE"), nullable=False
    )
    cve_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # Denormalized software identity. ``asset_software_id`` is a surrogate key
    # that churns when inventory is re-imported (a version change inserts a new
    # row), so reviewer decisions are re-associated on recompute by the stable
    # ``(software_vendor, software_product, cve_id)`` tuple — see
    # ``SqlAssetFindingRepository.replace_for_asset``.
    software_vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    software_product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # How the pairing was produced (e.g. ``cpe_matcher``). Distinct from the
    # asset_software ``source`` (where the inventory row came from).
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="cpe_matcher")
    cpe_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    epss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    kev_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    false_positive_reported_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    remediation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
