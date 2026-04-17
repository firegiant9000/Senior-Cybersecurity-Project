"""Repoint ai_summary_feedback FK from findings_snapshot to ai_summary_generation.

Revision ID: 019
Revises: 018
Create Date: 2026-04-17 00:00:00.000000

Steps:
  1. Add nullable ai_summary_generation_id FK column.
  2. Best-effort backfill: link feedback rows to the newest generation whose
     findings_snapshot_id matches feedback.summary_snapshot_id.
  3. Drop summary_snapshot_id column.

Historical feedback rows without a matching generation remain nullable.
downgrade restores summary_snapshot_id as nullable (data loss on backfill is acceptable).
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ai_summary_feedback
        ADD COLUMN IF NOT EXISTS ai_summary_generation_id INTEGER
            REFERENCES ai_summary_generations(id) ON DELETE SET NULL
        """
    )

    op.execute(
        """
        UPDATE ai_summary_feedback f
        SET ai_summary_generation_id = g.id
        FROM (
            SELECT DISTINCT ON (findings_snapshot_id)
                id, findings_snapshot_id, org_id
            FROM ai_summary_generations
            WHERE findings_snapshot_id IS NOT NULL
            ORDER BY findings_snapshot_id, generated_at DESC
        ) g
        WHERE f.summary_snapshot_id = g.findings_snapshot_id
          AND f.org_id = g.org_id
          AND f.ai_summary_generation_id IS NULL
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_summary_feedback_generation_id "
        "ON ai_summary_feedback (ai_summary_generation_id)"
    )

    op.execute(
        "ALTER TABLE ai_summary_feedback DROP COLUMN IF EXISTS summary_snapshot_id"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ai_summary_feedback
        ADD COLUMN IF NOT EXISTS summary_snapshot_id INTEGER
            REFERENCES findings_snapshots(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_ai_summary_feedback_generation_id"
    )
    op.execute(
        "ALTER TABLE ai_summary_feedback DROP COLUMN IF EXISTS ai_summary_generation_id"
    )
