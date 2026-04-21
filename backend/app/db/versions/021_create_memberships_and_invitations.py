"""Create memberships/invitations tables for multi-tenant org access.

Revision ID: 024
Revises: 023
Create Date: 2026-04-20 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "org_id", name="uq_memberships_user_org"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_org_id", "memberships", ["org_id"])
    op.create_index("ix_memberships_org_status", "memberships", ["org_id", "status"])

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inviter_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_invitations_org_id", "invitations", ["org_id"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
    op.create_index(
        "ix_invitations_pending",
        "invitations",
        ["org_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO memberships (user_id, org_id, role, status, created_at, updated_at)
            SELECT u.id,
                   u.org_id,
                   COALESCE(NULLIF(u.org_role, ''), 'member'),
                   'active',
                   COALESCE(u.created_at, now()),
                   now()
            FROM users u
            WHERE u.org_id IS NOT NULL
            ON CONFLICT (user_id, org_id) DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO invitations (email, org_id, inviter_id, role, token, status, expires_at, created_at)
            SELECT oi.invited_email,
                   oi.org_id,
                   oi.invited_by,
                   oi.org_role,
                   oi.invite_token,
                   oi.status,
                   oi.expires_at,
                   oi.created_at
            FROM org_invites oi
            ON CONFLICT (token) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_invitations_pending", table_name="invitations")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_index("ix_invitations_org_id", table_name="invitations")
    op.drop_table("invitations")

    op.drop_index("ix_memberships_org_status", table_name="memberships")
    op.drop_index("ix_memberships_org_id", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_table("memberships")
