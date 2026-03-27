"""Create organizations table and add org columns to users.

Revision ID: 005
Revises: 004
Create Date: 2026-03-27 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    """Check whether a table already exists (handles create_all race)."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": name},
    )
    return result.scalar() is not None


def _column_exists(table: str, column: str) -> bool:
    """Check whether a column already exists on a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table "
            "AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    """Apply migration."""
    if not _table_exists("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("industry_label", sa.String(100), nullable=False),
            sa.Column("ic3_sector", sa.String(100), nullable=False),
            sa.Column("primary_state", sa.String(2), nullable=False),
            sa.Column("employee_range", sa.String(50), nullable=False),
            sa.Column("revenue_range", sa.String(50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _column_exists("users", "org_id"):
        op.add_column("users", sa.Column("org_id", sa.Integer(), nullable=True))
    if not _column_exists("users", "org_role"):
        op.add_column("users", sa.Column("org_role", sa.String(50), nullable=True))

    # FK and index are safe to create even if columns were auto-created,
    # because create_all doesn't generate the named FK constraint.
    conn = op.get_bind()
    fk_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'fk_users_org_id' AND table_name = 'users'"
        )
    ).scalar()
    if not fk_exists:
        op.create_foreign_key(
            "fk_users_org_id",
            "users",
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="SET NULL",
        )

    ix_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_users_org_id'")
    ).scalar()
    if not ix_exists:
        op.create_index("ix_users_org_id", "users", ["org_id"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_constraint("fk_users_org_id", "users", type_="foreignkey")
    op.drop_column("users", "org_role")
    op.drop_column("users", "org_id")
    op.drop_table("organizations")
