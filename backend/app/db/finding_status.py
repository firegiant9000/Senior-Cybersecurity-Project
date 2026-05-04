"""FindingStatus ORM model — tracks per-finding remediation state for an org."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FindingStatus(Base):
    __tablename__ = "finding_statuses"
    __table_args__ = (UniqueConstraint("org_id", "stable_key", name="uq_finding_status_org_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stable_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    # Denormalized at PATCH time so the risk-score credit is decoupled from
    # snapshot freshness — without these, computing the credit requires the
    # latest findings_snapshot to still contain matching stable_keys, which
    # breaks for orgs that haven't re-opened the Findings tab since the
    # stable_key column was introduced.
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
