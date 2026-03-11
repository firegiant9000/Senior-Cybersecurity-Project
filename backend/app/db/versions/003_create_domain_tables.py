"""Create domain tables (cves, kev_catalog, ic3_incidents, economic_indicators).

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    # Use if_not_exists=True so this migration is safe to run on databases
    # where the tables were already created via Base.metadata.create_all().

    op.create_table(
        "cves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cve_id", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(op.f("ix_cves_cve_id"), "cves", ["cve_id"], unique=True, if_not_exists=True)
    op.create_index(op.f("ix_cves_cvss_score"), "cves", ["cvss_score"], if_not_exists=True)

    op.create_table(
        "kev_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cve_id", sa.String(50), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=False),
        sa.Column("product", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cve_id"], ["cves.cve_id"]),
        sa.UniqueConstraint("cve_id"),
        if_not_exists=True,
    )

    op.create_table(
        "ic3_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("attack_type", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("complaint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loss_amount", sa.Float(), nullable=False),
        sa.Column("avg_loss_per_incident", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_ic3_attack_type", "ic3_incidents", ["attack_type"], if_not_exists=True)
    op.create_index("ix_ic3_state", "ic3_incidents", ["state"], if_not_exists=True)
    op.create_index("ix_ic3_year", "ic3_incidents", ["year"], if_not_exists=True)

    op.create_table(
        "economic_indicators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("smb_count", sa.Integer(), nullable=False),
        sa.Column("avg_revenue", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_table("economic_indicators")
    op.drop_index("ix_ic3_year", table_name="ic3_incidents")
    op.drop_index("ix_ic3_state", table_name="ic3_incidents")
    op.drop_index("ix_ic3_attack_type", table_name="ic3_incidents")
    op.drop_table("ic3_incidents")
    op.drop_table("kev_catalog")
    op.drop_index(op.f("ix_cves_cvss_score"), table_name="cves")
    op.drop_index(op.f("ix_cves_cve_id"), table_name="cves")
    op.drop_table("cves")
