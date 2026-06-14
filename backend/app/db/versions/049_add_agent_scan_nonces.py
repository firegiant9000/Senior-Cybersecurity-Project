"""Add agent_scan_nonces (Month 4 Phase 3 — scan-upload replay guard).

Records the ``(scan_id, nonce)`` pair of every accepted agent scan upload so a
captured payload re-POSTed inside the replay window is rejected. The unique
constraint enforces this under concurrent double-submits; a cleanup sweep prunes
rows older than the window (``AGENT_SCAN_REPLAY_WINDOW_HOURS``).

Revision ID: 049
Revises: 048
Create Date: 2026-06-13 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: str | None = "048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "agent_scan_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("agent_enrollment_id", sa.Integer(), nullable=True),
        sa.Column("scan_id", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column(
            "seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_enrollment_id"], ["agent_enrollments.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "nonce", name="uq_agent_scan_nonces_scan_nonce"),
    )
    op.create_index("ix_agent_scan_nonces_org_id", "agent_scan_nonces", ["org_id"])
    op.create_index("ix_agent_scan_nonces_seen_at", "agent_scan_nonces", ["seen_at"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_agent_scan_nonces_seen_at", table_name="agent_scan_nonces")
    op.drop_index("ix_agent_scan_nonces_org_id", table_name="agent_scan_nonces")
    op.drop_table("agent_scan_nonces")
