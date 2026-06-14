"""AgentEnrollment ORM model — one bearer credential per read-only host agent.

Trust model is frozen in ``docs/month_4_phase0_closeout.md`` (Step 2). Key points
this table enforces:

* One row **per agent (per host)** so a single host can be revoked without
  touching the others.
* We store ``token_hash`` (sha256 of the secret) + ``token_prefix`` only; the
  raw secret is returned once at issue time and never persisted (mirrors SSH
  keys / personal access tokens).
* ``revoked_at`` doubles as the rotation grace marker: a live revoke sets it to
  ``now`` (rejected immediately); a rotation sets the *old* row's ``revoked_at``
  to ``now + grace`` so its token keeps working for the grace window. A token is
  valid only while ``revoked_at`` is null or still in the future.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentEnrollment(Base):
    __tablename__ = "agent_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # sha256(secret) as hex (64 chars). Raw secret is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Public lookup handle embedded in the bearer token; unique so the prefix
    # alone resolves exactly one row during verification.
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Null = active. <= now = revoked. > now = rotation grace window still open.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
