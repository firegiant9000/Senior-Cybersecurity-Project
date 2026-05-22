"""Add activation_events table for onboarding-funnel analytics.

Phase F4 (Month 2): lightweight client-side event log to measure whether
the onboarding-collapse work (Phase B) actually shortens time-to-value.

Only non-PII metadata is stored. Payloads pass through the observability
scrubber on the way in.

Revision ID: 039
Revises: 038
Create Date: 2026-05-21 00:00:11.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "activation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activation_events_org_event",
        "activation_events",
        ["org_id", "event_type"],
    )
    op.create_index(
        "ix_activation_events_occurred_at",
        "activation_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_activation_events_occurred_at", table_name="activation_events")
    op.drop_index("ix_activation_events_org_event", table_name="activation_events")
    op.drop_table("activation_events")
