"""Clear the legacy org fields of members who were removed from that org.

Removal used to deactivate the membership and then clear ``users.org_id`` / ``org_role`` in a
second commit, so a failure between the two could leave a removed user with legacy access.
Removal is now one transaction; this backfill repairs rows the old flow already left behind:
a user whose legacy ``org_id`` points at an org where they have a non-active membership and no
active one.

Data only, no schema change.

Revision ID: 052
Revises: 051
Create Date: 2026-10-24 00:00:00.000000

downgrade is a no-op: the cleared values are deliberately discarded (restoring them would
restore access that was revoked), so this data migration is irreversible.
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: str | None = "051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Module-level so a test can run exactly this statement.
CLEAR_STALE_LEGACY_ACCESS_SQL = """
UPDATE users
SET org_id = NULL, org_role = NULL
WHERE org_id IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.user_id = users.id AND m.org_id = users.org_id AND m.status <> 'active'
  )
  AND NOT EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.user_id = users.id AND m.org_id = users.org_id AND m.status = 'active'
  )
"""


def upgrade() -> None:
    """Apply migration."""
    op.execute(sa.text(CLEAR_STALE_LEGACY_ACCESS_SQL))


def downgrade() -> None:
    """Irreversible data migration: nothing to revert."""
