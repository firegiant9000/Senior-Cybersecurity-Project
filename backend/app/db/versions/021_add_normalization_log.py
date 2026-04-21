"""Add normalization_log table.

Revision ID: 021
Revises: 020
Create Date: 2026-04-20 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": name},
    )
    return result.scalar() is not None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    """Apply migration."""
    if not _table_exists("normalization_log"):
        op.create_table(
            "normalization_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("data_type", sa.String(length=50), nullable=False),
            sa.Column("raw_value", sa.Text(), nullable=False),
            sa.Column("normalized_value", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
            sa.Column("method", sa.String(length=50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("ix_normalization_log_org"):
        op.create_index("ix_normalization_log_org", "normalization_log", ["org_id"])

    if not _index_exists("ix_normalization_log_type"):
        op.create_index("ix_normalization_log_type", "normalization_log", ["data_type"])


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_normalization_log_type"):
        op.drop_index("ix_normalization_log_type", table_name="normalization_log")
    if _index_exists("ix_normalization_log_org"):
        op.drop_index("ix_normalization_log_org", table_name="normalization_log")
    if _table_exists("normalization_log"):
        op.drop_table("normalization_log")
