"""Ingest run ORM model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestRun(Base):
    """Represents an ingestion pipeline run."""

    # pylint: disable=too-few-public-methods

    __tablename__ = "ingest_runs"

    id: Mapped[UUID] = mapped_column(  # noqa: A003
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    source: Mapped[str] = mapped_column(String(255), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 1 additions
    trigger: Mapped[str] = mapped_column(String(50), default="manual")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
