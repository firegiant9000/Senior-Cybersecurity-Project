"""Create org_uploads and org_domains tables.

Revision ID: 007
Revises: 006
Create Date: 2026-03-29 00:00:00.000000

"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": name},
    )
    return result.scalar() is not None


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
    # --- org_uploads table ---
    if not _table_exists("org_uploads"):
        op.create_table(
            "org_uploads",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "uploaded_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_filename", sa.String(512), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("upload_purpose", sa.String(100), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("ix_org_uploads_org_id"):
        op.create_index("ix_org_uploads_org_id", "org_uploads", ["org_id"])

    # --- org_domains table ---
    if not _table_exists("org_domains"):
        op.create_table(
            "org_domains",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "added_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("domain_name", sa.String(255), nullable=False),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
            sa.UniqueConstraint("org_id", "domain_name", name="uq_org_domain"),
        )

    if not _index_exists("ix_org_domains_org_id"):
        op.create_index("ix_org_domains_org_id", "org_domains", ["org_id"])


def downgrade() -> None:
    """Revert migration."""
    if _index_exists("ix_org_domains_org_id"):
        op.drop_index("ix_org_domains_org_id", table_name="org_domains")
    if _table_exists("org_domains"):
        op.drop_table("org_domains")

    if _index_exists("ix_org_uploads_org_id"):
        op.drop_index("ix_org_uploads_org_id", table_name="org_uploads")
    if _table_exists("org_uploads"):
        op.drop_table("org_uploads")
