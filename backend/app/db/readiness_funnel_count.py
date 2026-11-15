"""Daily anonymous counters for the public readiness check (#296). Counts only; nothing about a visitor."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReadinessFunnelCount(Base):
    __tablename__ = "readiness_funnel_counts"
    # The unique key doubles as the index for day-range reads, so no extra index.
    __table_args__ = (
        UniqueConstraint(
            "day", "version", "step", name="uq_readiness_funnel_counts_day_version_step"
        ),
        CheckConstraint("count >= 0", name="ck_readiness_funnel_counts_count_nonneg"),
    )

    id: Mapped[int] = mapped_column(  # noqa: A003
        BigInteger, primary_key=True, autoincrement=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    # "question_answered:" + a 64-char id is 82 chars; 96 leaves headroom.
    step: Mapped[str] = mapped_column(String(96), nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
