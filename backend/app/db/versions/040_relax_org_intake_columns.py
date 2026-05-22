"""Relax NOT NULL on org demographic fields; add intake skip / completion state.

Phase B2 / B3 of the Month 2 plan. Allows orgs to be created with only
name + primary_domain (the fast-path onboarding wedge) and persists
which intake steps the user dismissed so the wall doesn't re-pop on
later logins (R9 mitigation).

Revision ID: 040
Revises: 039
Create Date: 2026-05-22 00:00:01.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    # Widen nullability — existing rows are unaffected because they already
    # have values; new rows from the fast-path can now omit these.
    op.alter_column("organizations", "industry_label", nullable=True)
    op.alter_column("organizations", "ic3_sector", nullable=True)
    op.alter_column("organizations", "primary_state", nullable=True)
    op.alter_column("organizations", "employee_range", nullable=True)

    op.add_column(
        "organizations",
        sa.Column("intake_skipped_steps", sa.JSON(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("intake_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Revert migration. Only safe if every row still has all four demographics set."""
    op.drop_column("organizations", "intake_completed_at")
    op.drop_column("organizations", "intake_skipped_steps")
    op.alter_column("organizations", "employee_range", nullable=False)
    op.alter_column("organizations", "primary_state", nullable=False)
    op.alter_column("organizations", "ic3_sector", nullable=False)
    op.alter_column("organizations", "industry_label", nullable=False)
