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


def _fk_exists_on_column(table: str, column: str) -> str | None:
    """Return the constraint name of any FK on table.column, or None."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_schema = 'public' "
            "  AND tc.table_name = :table "
            "  AND kcu.column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.first()
    return row[0] if row else None


def _index_exists(name: str) -> bool:
    """Check whether an index exists by name."""
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

    # Detect any existing FK on users.org_id (may have been auto-created
    # by Base.metadata.create_all with a different name).
    existing_fk = _fk_exists_on_column("users", "org_id")
    if not existing_fk:
        op.create_foreign_key(
            "fk_users_org_id",
            "users",
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _index_exists("ix_users_org_id"):
        op.create_index("ix_users_org_id", "users", ["org_id"])


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_users_org_id"):
        op.drop_index("ix_users_org_id", table_name="users")

    fk_name = _fk_exists_on_column("users", "org_id")
    if fk_name:
        op.drop_constraint(fk_name, "users", type_="foreignkey")

    if _column_exists("users", "org_role"):
        op.drop_column("users", "org_role")
    if _column_exists("users", "org_id"):
        op.drop_column("users", "org_id")
    if _table_exists("organizations"):
        op.drop_table("organizations")
