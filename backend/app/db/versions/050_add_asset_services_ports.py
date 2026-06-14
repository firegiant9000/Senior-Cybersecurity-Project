"""Add assets.services + assets.listening_ports (Month 4 Phase 3 — agent observations).

The read-only scanner already collects running services (systemctl) and, behind
``--include-ports``, listening ports (ss). Phase 3 validated them but discarded
them. These two JSON columns persist the latest snapshot per asset so the data is
visible in the asset detail and available to the Month 5 internet-exposed-port
risk factor. They are nullable and only the agent ingest path populates them, so
existing CSV/M365 inventory is unaffected.

Revision ID: 050
Revises: 049
Create Date: 2026-06-13 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: str | None = "049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column("assets", sa.Column("services", sa.JSON(), nullable=True))
    op.add_column("assets", sa.Column("listening_ports", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("assets", "listening_ports")
    op.drop_column("assets", "services")
