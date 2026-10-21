"""ActivationEvent ORM model — onboarding-funnel analytics (Phase F4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivationEvent(Base):
    __tablename__ = "activation_events"
    # Named to match migration 039; the org_id lookup is served by the
    # (org_id, event_type) composite.
    __table_args__ = (
        Index("ix_activation_events_org_event", "org_id", "event_type"),
        Index("ix_activation_events_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
