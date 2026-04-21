"""Enable pg_trgm extension and add GIN trigram indexes for fuzzy vendor matching.

Revision ID: 022
Revises: 021
Create Date: 2026-04-20 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    """Apply migration."""
    # IF NOT EXISTS makes this safe to re-run
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    if not _index_exists("ix_kev_vendor_trgm"):
        op.execute(
            sa.text("CREATE INDEX ix_kev_vendor_trgm ON kev_catalog USING GIN (vendor gin_trgm_ops)")
        )

    if not _index_exists("ix_org_vendor_name_trgm"):
        op.execute(
            sa.text(
                "CREATE INDEX ix_org_vendor_name_trgm "
                "ON org_vendors USING GIN (vendor_name gin_trgm_ops)"
            )
        )


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_org_vendor_name_trgm"):
        op.drop_index("ix_org_vendor_name_trgm", table_name="org_vendors")
    if _index_exists("ix_kev_vendor_trgm"):
        op.drop_index("ix_kev_vendor_trgm", table_name="kev_catalog")
    # Extension is intentionally not dropped — other objects may depend on pg_trgm.
