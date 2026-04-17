"""AI Summary Generation ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AISummaryGeneration(Base):
    __tablename__ = "ai_summary_generations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # gemini | fallback
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # success | error | fallback_used
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rendered_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    findings_snapshot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("findings_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
