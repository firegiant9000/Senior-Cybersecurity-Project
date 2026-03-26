"""Add firebase_uid and auth_provider columns to users table.

Revision ID: 004
Revises: 003
Create Date: 2026-03-26 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    # Add firebase_uid column (nullable first so existing rows don't break)
    op.add_column("users", sa.Column("firebase_uid", sa.String(128), nullable=True))
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(50), nullable=False, server_default="email"),
    )

    # Make hashed_password nullable (Firebase manages passwords)
    op.alter_column("users", "hashed_password", existing_type=sa.String(255), nullable=True)

    # Create unique index on firebase_uid
    op.create_index(op.f("ix_users_firebase_uid"), "users", ["firebase_uid"], unique=True)


def downgrade() -> None:
    """Revert migration."""
    op.drop_index(op.f("ix_users_firebase_uid"), table_name="users")
    op.alter_column("users", "hashed_password", existing_type=sa.String(255), nullable=False)
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "firebase_uid")
