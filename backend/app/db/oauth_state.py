"""OAuthState ORM model — short-lived state tokens for OAuth flows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# pylint: disable=too-few-public-methods
class OAuthState(Base):
    """One-time, short-lived state token binding an OAuth roundtrip."""

    __tablename__ = "oauth_states"
    __table_args__ = (Index("ix_oauth_states_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    state_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
