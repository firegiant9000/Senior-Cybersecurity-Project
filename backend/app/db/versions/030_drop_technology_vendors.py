"""Drop orphan technology_vendors table.

The global technology_vendors catalog was never wired into the frontend and
is being removed in favor of the org-scoped org_vendors table. The planned
Month 3 vendor_aliases work supersedes any future need for a global catalog.

Revision ID: 030
Revises: 029
Create Date: 2026-05-20 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str | None = "029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.execute("DROP TABLE IF EXISTS technology_vendors")


def downgrade() -> None:
    """Revert migration."""
    op.create_table(
        "technology_vendors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(255), nullable=False, server_default=""),
        sa.Column("category", sa.String(255), nullable=False, server_default=""),
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
    )
