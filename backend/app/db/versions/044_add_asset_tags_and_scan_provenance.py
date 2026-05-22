"""Add tags + scan_run provenance to assets/asset_software.

Nice-to-haves N5 (asset tagging) and N9 (import history rollback) from
docs/month_2_execution_plan.md. Tags are a JSON array of strings on
``assets``; the per-row ``created_by_scan_run_id`` lets rollback delete
exactly the rows a given import created.

Revision ID: 044
Revises: 043
Create Date: 2026-05-22 00:00:01.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: str | None = "043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "assets",
        sa.Column("tags", sa.JSON(), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column(
            "created_by_scan_run_id",
            sa.Integer(),
            sa.ForeignKey("scan_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_assets_created_by_scan_run",
        "assets",
        ["created_by_scan_run_id"],
    )

    op.add_column(
        "asset_software",
        sa.Column(
            "created_by_scan_run_id",
            sa.Integer(),
            sa.ForeignKey("scan_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_asset_software_created_by_scan_run",
        "asset_software",
        ["created_by_scan_run_id"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_asset_software_created_by_scan_run", table_name="asset_software")
    op.drop_column("asset_software", "created_by_scan_run_id")
    op.drop_index("ix_assets_created_by_scan_run", table_name="assets")
    op.drop_column("assets", "created_by_scan_run_id")
    op.drop_column("assets", "tags")
