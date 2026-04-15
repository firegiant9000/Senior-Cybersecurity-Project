"""Create ai_summary_feedback table.

Stores user ratings and flags for AI-generated summaries to inform prompt tuning.

Revision ID: 015
Revises: 014
Create Date: 2026-04-15 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use raw DDL with IF NOT EXISTS — the table may already exist if
    # Base.metadata.create_all() ran at startup before Alembic.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_summary_feedback (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL,
            flag VARCHAR(50) NOT NULL,
            comment TEXT,
            summary_snapshot_id INTEGER REFERENCES findings_snapshots(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_summary_feedback_org_id ON ai_summary_feedback (org_id)"
    )


def downgrade() -> None:
    op.drop_index("ix_ai_summary_feedback_org_id")
    op.drop_table("ai_summary_feedback")
