"""AI Summary Feedback ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AISummaryFeedback(Base):
    __tablename__ = "ai_summary_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    flag: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # helpful | inaccurate | too_vague | other
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_generation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_summary_generations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
