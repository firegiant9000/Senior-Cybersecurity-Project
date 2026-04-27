"""Make organizations.revenue_range nullable.

The ORM has declared revenue_range as nullable since the security-profile
migration, and the API schemas accept null ("Prefer not to say"), but the
column was created NOT NULL by migration 005. This brings the DB in line
with the model so onboarding/intake can submit without a revenue value.

Revision ID: 027
Revises: 026
Create Date: 2026-04-26 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "organizations",
        "revenue_range",
        existing_type=sa.String(50),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "organizations",
        "revenue_range",
        existing_type=sa.String(50),
        nullable=False,
    )
