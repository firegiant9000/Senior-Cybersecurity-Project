"""Extend ingest_runs with trigger, retry_count, skipped_reason, next_scheduled_at.

Revision ID: 016
Revises: 015
Create Date: 2026-04-15 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ingest_runs
            ADD COLUMN IF NOT EXISTS trigger VARCHAR(50) NOT NULL DEFAULT 'manual',
            ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS skipped_reason VARCHAR(255),
            ADD COLUMN IF NOT EXISTS next_scheduled_at TIMESTAMP
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ingest_runs
            DROP COLUMN IF EXISTS trigger,
            DROP COLUMN IF EXISTS retry_count,
            DROP COLUMN IF EXISTS skipped_reason,
            DROP COLUMN IF EXISTS next_scheduled_at
        """
    )
