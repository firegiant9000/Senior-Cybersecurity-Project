"""Create asset_software table.

Revision ID: 035
Revises: 034
Create Date: 2026-05-21 00:00:02.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "asset_software",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor", sa.String(255), nullable=False),
        sa.Column("product", sa.String(255), nullable=False),
        sa.Column("version", sa.String(100), nullable=True),
        sa.Column("cpe_uri", sa.String(500), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
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
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_software_org_id", "asset_software", ["org_id"])
    op.create_index("ix_asset_software_asset_id", "asset_software", ["asset_id"])
    op.create_index(
        "ix_asset_software_org_vendor_product",
        "asset_software",
        ["org_id", "vendor", "product"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_asset_software_org_vendor_product", table_name="asset_software")
    op.drop_index("ix_asset_software_asset_id", table_name="asset_software")
    op.drop_index("ix_asset_software_org_id", table_name="asset_software")
    op.drop_table("asset_software")
