"""Add organizations.is_demo + create audit_log table.

Two related changes land in a single migration so the new demo segregation
(per-org is_demo flag) and the new data-lifecycle endpoints (DELETE/export
both write an audit_log row) ship together.

Revision ID: 031
Revises: 030
Create Date: 2026-05-20 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: str | None = "030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "organizations",
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_organizations_is_demo ON organizations (is_demo)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
            action VARCHAR(64) NOT NULL,
            payload JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_org_id ON audit_log (org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log (created_at DESC)")


def downgrade() -> None:
    """Revert migration."""
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP INDEX IF EXISTS ix_organizations_is_demo")
    op.drop_column("organizations", "is_demo")
