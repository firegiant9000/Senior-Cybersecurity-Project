"""Add epss_score column to cves table.

EPSS (Exploit Prediction Scoring System) provides a 0-1 probability that a CVE
will be exploited in the wild within 30 days. Populated by the EPSS ingestor.

Revision ID: 025
Revises: 024
Create Date: 2026-04-21 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "cves",
        sa.Column("epss_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("cves", "epss_score")
