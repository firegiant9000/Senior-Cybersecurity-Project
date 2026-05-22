"""Add oauth_states table for short-lived OAuth state tokens.

Used by the M365/Entra consent flow (Phase E3) to bind a consent
roundtrip to the initiating user/org. Rows are single-use and pruned on
read; expiry caps blast radius if the table is forgotten.

Revision ID: 042
Revises: 040
Create Date: 2026-05-22 00:00:02.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("state_token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("redirect_uri", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_states_state_token", "oauth_states", ["state_token"], unique=True)
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state_token", table_name="oauth_states")
    op.drop_table("oauth_states")
