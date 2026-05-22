"""Add external-check cache columns to org_domains.

Adds persistent 24h per-domain caching for HIBP / Shodan / OTX one-shot
lookups so we never burn an upstream quota credit twice within the window.

Revision ID: 032
Revises: 031
Create Date: 2026-05-20 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032"
down_revision: str | None = "031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "org_domains",
        sa.Column(
            "external_checks_last_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "org_domains",
        sa.Column(
            "external_checks_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("org_domains", "external_checks_data")
    op.drop_column("org_domains", "external_checks_last_at")
