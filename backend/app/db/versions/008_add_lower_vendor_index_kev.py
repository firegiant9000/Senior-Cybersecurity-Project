"""Add functional index on LOWER(vendor) to kev_catalog for vendor-alerts JOIN.

Revision ID: 008
Revises: 007
Create Date: 2026-03-29 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    if not _index_exists("ix_kev_catalog_vendor_lower"):
        op.execute(
            sa.text("CREATE INDEX ix_kev_catalog_vendor_lower ON kev_catalog (LOWER(vendor))")
        )


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_kev_catalog_vendor_lower"):
        op.drop_index("ix_kev_catalog_vendor_lower", table_name="kev_catalog")
