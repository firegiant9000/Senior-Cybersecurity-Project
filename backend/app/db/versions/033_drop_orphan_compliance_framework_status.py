"""Drop orphan organizations.compliance_framework_status column.

The column was added in migration 026 but the ORM model lost the attribute
in a later refactor with no follow-up migration to remove it from the DB.
``alembic check`` flagged the divergence. The column is referenced nowhere
in the application code, so dropping it removes the drift without affecting
behaviour.

Revision ID: 033
Revises: 032
Create Date: 2026-05-21 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.drop_column("organizations", "compliance_framework_status")


def downgrade() -> None:
    """Revert migration."""
    op.add_column(
        "organizations",
        sa.Column("compliance_framework_status", sa.JSON(), nullable=True),
    )
