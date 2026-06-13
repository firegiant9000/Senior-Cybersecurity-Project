"""Create cve_cpe_match table (per-CVE CPE criteria + version ranges).

Phase 1 of docs/month_3_execution_plan.md. Stores the affected-version ranges
NVD publishes in CPE configurations, which were previously discarded. Distinct
from cpe_match_cache (normalized-name → CPE lookup); this is the CVE →
affected-version-ranges source of truth the Month 3 matcher reads.

Revision ID: 045
Revises: 044
Create Date: 2026-06-12 00:00:01.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: str | None = "044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "cve_cpe_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cve_id", sa.String(50), nullable=False),
        sa.Column("cpe_uri", sa.String(500), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("product", sa.String(255), nullable=True),
        sa.Column("version_start_including", sa.String(100), nullable=True),
        sa.Column("version_start_excluding", sa.String(100), nullable=True),
        sa.Column("version_end_including", sa.String(100), nullable=True),
        sa.Column("version_end_excluding", sa.String(100), nullable=True),
        sa.Column("vulnerable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cve_cpe_match_cve_id", "cve_cpe_match", ["cve_id"])
    op.create_index(
        "ix_cve_cpe_match_vendor_product",
        "cve_cpe_match",
        ["vendor", "product"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_cve_cpe_match_vendor_product", table_name="cve_cpe_match")
    op.drop_index("ix_cve_cpe_match_cve_id", table_name="cve_cpe_match")
    op.drop_table("cve_cpe_match")
