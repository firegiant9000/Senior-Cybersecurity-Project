"""Add agent_enrollments (Month 4 Phase 1 — agent trust model).

Per-agent bearer credential for the read-only host scanner. Columns are frozen
in ``docs/month_4_phase0_closeout.md`` Step 2: ``token_hash`` + ``token_prefix``
(never the raw secret), ``scopes`` (JSON), and ``revoked_at`` which doubles as
the rotation grace marker (null = active, <= now = revoked, > now = grace open).
Indexed on ``org_id`` and a unique ``token_prefix`` for verification lookups.

Revision ID: 048
Revises: 047
Create Date: 2026-06-13 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "048"
down_revision: str | None = "047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "agent_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_prefix", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_enrollments_org_id", "agent_enrollments", ["org_id"])
    op.create_index(
        "ix_agent_enrollments_token_prefix",
        "agent_enrollments",
        ["token_prefix"],
        unique=True,
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_agent_enrollments_token_prefix", table_name="agent_enrollments")
    op.drop_index("ix_agent_enrollments_org_id", table_name="agent_enrollments")
    op.drop_table("agent_enrollments")
