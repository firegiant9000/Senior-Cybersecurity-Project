"""Add composite index on (sector, state, year) to ic3_incidents for loss projection.

Revision ID: 009
Revises: 008
Create Date: 2026-04-08 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_ic3_sector_state_year"


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": name},
        ).scalar()
        is not None
    )


def upgrade() -> None:
    """Apply migration."""
    if not _index_exists(INDEX_NAME):
        op.create_index(
            INDEX_NAME,
            "ic3_incidents",
            ["sector", "state", "year"],
        )


def downgrade() -> None:
    """Revert migration."""
    if _index_exists(INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="ic3_incidents")
