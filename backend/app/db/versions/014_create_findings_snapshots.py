"""Create findings_snapshots table.

Stores historical findings reports for audit trails and trend tracking.

Revision ID: 014
Revises: 013
Create Date: 2026-04-15 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use raw DDL with IF NOT EXISTS — the table may already exist if
    # Base.metadata.create_all() ran at startup before Alembic.
    op.execute("""
        CREATE TABLE IF NOT EXISTS findings_snapshots (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            findings JSON NOT NULL,
            summary JSON NOT NULL,
            assessment_tier VARCHAR(50) NOT NULL,
            data_sources_used JSON NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_snapshots_org_id ON findings_snapshots (org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_snapshots_generated_at ON findings_snapshots (generated_at)")


def downgrade() -> None:
    op.drop_index("ix_findings_snapshots_generated_at")
    op.drop_index("ix_findings_snapshots_org_id")
    op.drop_table("findings_snapshots")
