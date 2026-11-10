"""Widen asset columns to the agent upload schema's string caps.

The frozen agent wire contract (``app/schemas/agent_scan.py``) accepts longer strings than these
columns held, so a payload that passed validation failed at insert with a 500 (issue #246).
``cpe_match_cache.version_normalized`` is widened too: the CPE matcher caches the lowercased
software version there (and skips caching one that lowercasing lengthened past 255).

Widening a varchar is a metadata-only change in PostgreSQL (no table rewrite).

Revision ID: 053
Revises: 052
Create Date: 2026-11-09 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "053"
down_revision: str | None = "052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, old length, new length)
_WIDENED = (
    ("assets", "ip_address", 45, 64),
    ("assets", "os_name", 100, 128),
    ("assets", "os_version", 100, 128),
    ("asset_software", "version", 100, 255),
    ("cpe_match_cache", "version_normalized", 100, 255),
)


def upgrade() -> None:
    """Apply migration."""
    # The ALTERs take ACCESS EXCLUSIVE locks (held until commit) while the old instance still
    # serves traffic. Each waits at most 5s for a blocker, so a stuck deploy fails (retryable)
    # within seconds instead of queueing asset reads indefinitely.
    op.execute("SET LOCAL lock_timeout = '5s'")
    for table, column, old, new in _WIDENED:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(old),
            type_=sa.String(new),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Revert migration. Fails if any row now holds a value longer than the old length."""
    for table, column, old, new in reversed(_WIDENED):
        op.alter_column(
            table,
            column,
            existing_type=sa.String(new),
            type_=sa.String(old),
            existing_nullable=True,
        )
