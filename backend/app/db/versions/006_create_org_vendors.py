"""Create org_vendors table for technology stack tracking.

Revision ID: 006
Revises: 005
Create Date: 2026-03-28 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": name},
    )
    return result.scalar() is not None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": name},
        ).scalar()
        is not None
    )


def upgrade() -> None:
    """Apply migration."""
    if not _table_exists("org_vendors"):
        op.create_table(
            "org_vendors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("vendor_name", sa.String(255), nullable=False),
            sa.Column("product_name", sa.String(255), nullable=False, server_default=""),
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
            sa.UniqueConstraint("org_id", "vendor_name", "product_name", name="uq_org_vendor_product"),
        )

    if not _index_exists("ix_org_vendors_org_id"):
        op.create_index("ix_org_vendors_org_id", "org_vendors", ["org_id"])

    # Index on kev_catalog.vendor for autocomplete performance
    if not _index_exists("ix_kev_catalog_vendor"):
        op.create_index("ix_kev_catalog_vendor", "kev_catalog", ["vendor"])


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_kev_catalog_vendor"):
        op.drop_index("ix_kev_catalog_vendor", table_name="kev_catalog")
    if _index_exists("ix_org_vendors_org_id"):
        op.drop_index("ix_org_vendors_org_id", table_name="org_vendors")
    if _table_exists("org_vendors"):
        op.drop_table("org_vendors")
