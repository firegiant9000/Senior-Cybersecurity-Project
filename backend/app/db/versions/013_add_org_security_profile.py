"""Add security profile fields to organizations table.

Adds: security_controls, cloud_providers, compliance_frameworks, data_types,
      device_count_range, incident_history

Revision ID: 013
Revises: 012
Create Date: 2026-04-14 00:00:00.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("security_controls", sa.JSON(), nullable=True))
    op.add_column("organizations", sa.Column("cloud_providers", sa.JSON(), nullable=True))
    op.add_column("organizations", sa.Column("compliance_frameworks", sa.JSON(), nullable=True))
    op.add_column("organizations", sa.Column("data_types", sa.JSON(), nullable=True))
    op.add_column("organizations", sa.Column("device_count_range", sa.String(50), nullable=True))
    op.add_column("organizations", sa.Column("incident_history", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "incident_history")
    op.drop_column("organizations", "device_count_range")
    op.drop_column("organizations", "data_types")
    op.drop_column("organizations", "compliance_frameworks")
    op.drop_column("organizations", "cloud_providers")
    op.drop_column("organizations", "security_controls")
