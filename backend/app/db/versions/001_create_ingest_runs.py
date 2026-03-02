"""Initial migration - Create ingest_runs table.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "ingest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("records_ingested", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_runs_source"), "ingest_runs", ["source"])
    op.create_index(op.f("ix_ingest_runs_started_at"), "ingest_runs", ["started_at"])
    op.create_index(op.f("ix_ingest_runs_status"), "ingest_runs", ["status"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index(op.f("ix_ingest_runs_status"), table_name="ingest_runs")
    op.drop_index(op.f("ix_ingest_runs_started_at"), table_name="ingest_runs")
    op.drop_index(op.f("ix_ingest_runs_source"), table_name="ingest_runs")
    op.drop_table("ingest_runs")
