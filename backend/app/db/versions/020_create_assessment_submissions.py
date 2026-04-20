"""Create assessment_submissions table.

Revision ID: 020
Revises: 019
Create Date: 2026-04-20 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: str | None = "019"
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
    if not _table_exists("assessment_submissions"):
        op.create_table(
            "assessment_submissions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "version",
                name="uq_assessment_submissions_org_version",
            ),
        )

    if not _index_exists("ix_assessment_submissions_organization_id"):
        op.create_index(
            "ix_assessment_submissions_organization_id",
            "assessment_submissions",
            ["organization_id"],
        )
    if not _index_exists("ix_assessment_submissions_is_current"):
        op.create_index(
            "ix_assessment_submissions_is_current",
            "assessment_submissions",
            ["is_current"],
        )


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_assessment_submissions_is_current"):
        op.drop_index("ix_assessment_submissions_is_current", table_name="assessment_submissions")
    if _index_exists("ix_assessment_submissions_organization_id"):
        op.drop_index(
            "ix_assessment_submissions_organization_id",
            table_name="assessment_submissions",
        )
    if _table_exists("assessment_submissions"):
        op.drop_table("assessment_submissions")
