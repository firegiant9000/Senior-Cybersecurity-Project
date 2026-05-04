"""Add denormalized title + severity columns to finding_statuses.

Lets the /mine/risk endpoint compute remediation credit purely from the
finding_statuses table, without needing the latest findings_snapshot to
still contain matching stable_keys. Solves the demo-time bug where some
finding categories (vendor_exposure, recommended_action) wouldn't move
the risk score because their stable_keys hadn't been written into a
snapshot yet.

Revision ID: 029
Revises: 028
Create Date: 2026-05-04 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "029"
down_revision: str | None = "028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE finding_statuses ADD COLUMN IF NOT EXISTS title VARCHAR(500)"
    )
    op.execute(
        "ALTER TABLE finding_statuses ADD COLUMN IF NOT EXISTS severity VARCHAR(20)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE finding_statuses DROP COLUMN IF EXISTS severity")
    op.execute("ALTER TABLE finding_statuses DROP COLUMN IF EXISTS title")
