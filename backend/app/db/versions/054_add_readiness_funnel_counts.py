"""Add readiness_funnel_counts table for anonymous public readiness-check counters.

Daily per-version, per-step counters (#296). Counts only: no IP, visitor id,
domain or answer is stored.

Revision ID: 054
Revises: 053
Create Date: 2026-11-15 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: str | None = "053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "readiness_funnel_counts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("step", sa.String(96), nullable=False),
        sa.Column("count", sa.BigInteger(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "day",
            "version",
            "step",
            name="uq_readiness_funnel_counts_day_version_step",
        ),
        sa.CheckConstraint("count >= 0", name="ck_readiness_funnel_counts_count_nonneg"),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_table("readiness_funnel_counts")
