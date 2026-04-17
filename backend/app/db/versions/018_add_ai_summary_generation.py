"""Add ai_summary_generations table.

Revision ID: 018
Revises: 017
Create Date: 2026-04-17 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_summary_generations (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            model_name VARCHAR(100) NOT NULL,
            source VARCHAR(20) NOT NULL,
            status VARCHAR(30) NOT NULL,
            error_message TEXT,
            prompt_inputs JSONB NOT NULL,
            rendered_prompt TEXT,
            output_text TEXT,
            output_meta JSONB,
            findings_snapshot_id INTEGER REFERENCES findings_snapshots(id) ON DELETE SET NULL,
            triggered_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            latency_ms INTEGER
        )
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_summary_generations_org_id "
        "ON ai_summary_generations (org_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_summary_generations_org_generated "
        "ON ai_summary_generations (org_id, generated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_summary_generations_org_generated")
    op.execute("DROP INDEX IF EXISTS ix_ai_summary_generations_org_id")
    op.drop_table("ai_summary_generations")
