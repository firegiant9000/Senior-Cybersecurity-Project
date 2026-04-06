"""Add logo URL and primary domain to organizations.

Revision ID: 009
Revises: 008
Create Date: 2026-04-03 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table "
            "AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not _column_exists("organizations", "logo_url"):
        op.add_column(
            "organizations",
            sa.Column("logo_url", sa.String(500), nullable=True),
        )
    if not _column_exists("organizations", "primary_domain"):
        op.add_column(
            "organizations",
            sa.Column("primary_domain", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("organizations", "primary_domain"):
        op.drop_column("organizations", "primary_domain")
    if _column_exists("organizations", "logo_url"):
        op.drop_column("organizations", "logo_url")
