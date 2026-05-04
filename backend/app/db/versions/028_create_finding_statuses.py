"""Create finding_statuses table for per-finding remediation state.

Stores user-driven status (open/done/dismissed) keyed by a stable identity
that survives findings_engine re-ingest. Joined into GET /mine/findings to
hydrate each Finding's status, and aggregated into a remediation credit
deducted from the org's risk score.

Revision ID: 028
Revises: 027
Create Date: 2026-05-03 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "028"
down_revision: str | None = "027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_statuses (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            stable_key VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_finding_status_org_key UNIQUE (org_id, stable_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_finding_statuses_org_id ON finding_statuses (org_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_finding_statuses_org_id")
    op.execute("DROP TABLE IF EXISTS finding_statuses")
