"""Add epss_percentile and epss_fetched_at columns to cves.

Phase D2 (Month 2): the EPSS ingestor previously wrote only ``epss_score``
(migration 025). The Exploitability surface in the NVD table needs the
percentile rank and a fetched-at timestamp so widgets can show staleness.

Revision ID: 038
Revises: 037
Create Date: 2026-05-21 00:00:10.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: str | None = "037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column("cves", sa.Column("epss_percentile", sa.Float(), nullable=True))
    op.add_column(
        "cves",
        sa.Column("epss_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("cves", "epss_fetched_at")
    op.drop_column("cves", "epss_percentile")
