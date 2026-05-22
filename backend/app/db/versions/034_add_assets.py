"""Create assets table for inventory tracking.

Revision ID: 034
Revises: 033
Create Date: 2026-05-21 00:00:01.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("os_name", sa.String(100), nullable=True),
        sa.Column("os_version", sa.String(100), nullable=True),
        sa.Column("mac_address", sa.String(64), nullable=True),
        sa.Column("discovered_via", sa.String(32), nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_org_id", "assets", ["org_id"])
    op.create_index("ix_assets_org_hostname", "assets", ["org_id", "hostname"])
    op.create_index("ix_assets_org_is_active", "assets", ["org_id", "is_active"])
    # NULL-safe uniqueness on (org_id, hostname, mac_address). COALESCE lets
    # rows without a MAC still collide on (org_id, hostname).
    op.execute(
        "CREATE UNIQUE INDEX uq_assets_org_host_mac "
        "ON assets (org_id, hostname, COALESCE(mac_address, ''))"
    )


def downgrade() -> None:
    """Revert migration."""
    op.execute("DROP INDEX IF EXISTS uq_assets_org_host_mac")
    op.drop_index("ix_assets_org_is_active", table_name="assets")
    op.drop_index("ix_assets_org_hostname", table_name="assets")
    op.drop_index("ix_assets_org_id", table_name="assets")
    op.drop_table("assets")
