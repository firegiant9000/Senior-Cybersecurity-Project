"""Add compliance_framework_status tri-state column to organizations.

Stores per-framework status as {"HIPAA": "yes"|"no"|"unsure", ...}.
The legacy compliance_frameworks list[str] column is preserved and continues
to mean "frameworks the org has" (status=yes), so existing consumers keep
working.

Revision ID: 026
Revises: 025
Create Date: 2026-04-25 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("compliance_framework_status", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "compliance_framework_status")
