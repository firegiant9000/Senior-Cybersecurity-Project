"""Add denormalized software identity to asset_findings.

Stores ``software_vendor`` / ``software_product`` on each finding so reviewer
decisions (status, false-positive reports, remediation notes) survive a
re-import that re-keys ``asset_software`` to a new surrogate id. Columns are
nullable and backfill themselves on the next matcher recompute.

Revision ID: 047
Revises: 046
Create Date: 2026-06-13 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "asset_findings",
        sa.Column("software_vendor", sa.String(255), nullable=True),
    )
    op.add_column(
        "asset_findings",
        sa.Column("software_product", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("asset_findings", "software_product")
    op.drop_column("asset_findings", "software_vendor")
