"""Create scan_runs table — one row per inventory ingest event.

Revision ID: 036
Revises: 035
Create Date: 2026-05-21 00:00:03.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: str | None = "035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "asset_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "software_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "triggered_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_runs_org_id", "scan_runs", ["org_id"])
    op.create_index("ix_scan_runs_org_started", "scan_runs", ["org_id", "started_at"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_scan_runs_org_started", table_name="scan_runs")
    op.drop_index("ix_scan_runs_org_id", table_name="scan_runs")
    op.drop_table("scan_runs")
