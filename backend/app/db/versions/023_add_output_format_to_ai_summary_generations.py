"""Add output_format column to ai_summary_generations.

Distinguishes JSON-structured rows (post-Gemini JSON mode) from legacy prose rows
so history viewers can parse output_text correctly.

Revision ID: 023
Revises: 022
Create Date: 2026-04-20 00:00:00.000000
"""

# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "ai_summary_generations",
        sa.Column(
            "output_format",
            sa.String(10),
            nullable=False,
            server_default="prose",
        ),
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_column("ai_summary_generations", "output_format")
