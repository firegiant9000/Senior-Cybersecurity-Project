"""AgentScanNonce ORM model — replay guard for agent scan uploads (Month 4 Phase 3).

Each accepted upload records its ``(scan_id, nonce)`` pair. A re-submitted pair
seen inside the configured window (``AGENT_SCAN_REPLAY_WINDOW_HOURS``) is rejected
as a replay. The unique constraint enforces this even under a concurrent double
POST; a cleanup sweep prunes rows older than the window so the table stays bounded
(the duplicate-within-window check is what actually matters, not permanent
uniqueness).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentScanNonce(Base):
    __tablename__ = "agent_scan_nonces"
    __table_args__ = (UniqueConstraint("scan_id", "nonce", name="uq_agent_scan_nonces_scan_nonce"),)

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The enrollment that submitted the payload; SET NULL so revoking an agent
    # does not drop its replay history mid-window.
    agent_enrollment_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_enrollments.id", ondelete="SET NULL"), nullable=True
    )
    scan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
