"""Create asset_findings table + assets.asset_criticality.

Phase 3 of docs/month_3_execution_plan.md. Persists version-aware CVE matches
(produced by the Phase 2 CpeMatcher) with their confidence tier, per-finding
risk score, and a remediation status workflow, so findings are stored once
rather than recomputed in-memory on every request. ``asset_criticality`` feeds
the per-finding risk scorer.

Revision ID: 046
Revises: 045
Create Date: 2026-06-12 00:00:02.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "assets",
        sa.Column(
            "asset_criticality",
            sa.String(20),
            nullable=False,
            server_default="normal",
        ),
    )

    op.create_table(
        "asset_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("asset_software_id", sa.Integer(), nullable=False),
        sa.Column("cve_id", sa.String(50), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="cpe_matcher"),
        sa.Column("cpe_uri", sa.String(500), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("epss_score", sa.Float(), nullable=True),
        sa.Column("kev_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("match_confidence", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("false_positive_reported_by", sa.Integer(), nullable=True),
        sa.Column("remediation_summary", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_software_id"], ["asset_software.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["false_positive_reported_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_software_id", "cve_id", name="uq_asset_finding_software_cve"),
    )
    op.create_index("ix_asset_findings_org_asset", "asset_findings", ["org_id", "asset_id"])
    op.create_index("ix_asset_findings_org_status", "asset_findings", ["org_id", "status"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_asset_findings_org_status", table_name="asset_findings")
    op.drop_index("ix_asset_findings_org_asset", table_name="asset_findings")
    op.drop_table("asset_findings")
    op.drop_column("assets", "asset_criticality")
