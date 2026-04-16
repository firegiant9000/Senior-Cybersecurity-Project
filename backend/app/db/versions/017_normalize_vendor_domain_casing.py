"""Normalize vendor and domain casing — backfill existing data.

Revision ID: 017
Revises: 016
Create Date: 2026-04-15 00:00:00.000000

Steps (in order):
  1. Delete case-duplicate vendors (keep lowest id per org+lower(vendor)+lower(product)).
  2. Normalize vendor_name whitespace (trim + collapse runs to single space).
  3. Delete case-duplicate domains (keep lowest id per org+lower(domain)).
  4. Normalize domain_name to lowercase + trim.

downgrade is a no-op — this is a lossy data migration.
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Remove case-duplicate org_vendors — keep the row with the lowest id.
    op.execute(
        """
        DELETE FROM org_vendors
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY org_id, LOWER(vendor_name), LOWER(product_name)
                           ORDER BY id
                       ) AS rn
                FROM org_vendors
            ) ranked
            WHERE rn > 1
        )
        """
    )

    # 2. Normalize vendor_name: trim + collapse consecutive whitespace.
    op.execute(
        r"""
        UPDATE org_vendors
        SET vendor_name = TRIM(REGEXP_REPLACE(vendor_name, '\s+', ' ', 'g'))
        WHERE vendor_name != TRIM(REGEXP_REPLACE(vendor_name, '\s+', ' ', 'g'))
        """
    )

    # 3. Remove case-duplicate org_domains — keep the row with the lowest id.
    op.execute(
        """
        DELETE FROM org_domains
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY org_id, LOWER(domain_name)
                           ORDER BY id
                       ) AS rn
                FROM org_domains
            ) ranked
            WHERE rn > 1
        )
        """
    )

    # 4. Normalize domain_name: lowercase + trim.
    op.execute(
        """
        UPDATE org_domains
        SET domain_name = LOWER(TRIM(domain_name))
        WHERE domain_name != LOWER(TRIM(domain_name))
        """
    )


def downgrade() -> None:
    # Data normalization is irreversible — no-op.
    pass
