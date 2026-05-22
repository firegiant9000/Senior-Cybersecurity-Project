"""IntegrationCredential ORM model — per-org OAuth-connected integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# pylint: disable=too-few-public-methods
class IntegrationCredential(Base):
    """Encrypted OAuth credentials for a third-party integration."""

    __tablename__ = "integration_credentials"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="uq_integration_credentials_org_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connected_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
