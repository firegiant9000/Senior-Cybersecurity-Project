"""Add agent_enrollments.chain_root_id (agent-token lifecycle: revoke the rotation chain).

A rotation creates a successor row. ``chain_root_id`` links every successor to the original
row of its chain (NULL on the original), so revoking any row can revoke the whole chain with
one indexed UPDATE. Rotations done before this migration are not linked.

Revision ID: 051
Revises: 050
Create Date: 2026-10-23 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: str | None = "050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column("agent_enrollments", sa.Column("chain_root_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_agent_enrollments_chain_root_id",
        "agent_enrollments",
        "agent_enrollments",
        ["chain_root_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_enrollments_chain_root_id", "agent_enrollments", ["chain_root_id"], unique=False
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_agent_enrollments_chain_root_id", table_name="agent_enrollments")
    op.drop_constraint(
        "fk_agent_enrollments_chain_root_id", "agent_enrollments", type_="foreignkey"
    )
    op.drop_column("agent_enrollments", "chain_root_id")
