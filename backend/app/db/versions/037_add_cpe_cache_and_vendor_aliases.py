"""Create cpe_match_cache and vendor_aliases tables.

Per Phase A4/A5 of docs/month_2_execution_plan.md. The CPE cache is
pre-staged empty so the Month 3 matcher service can be developed against
a real schema; vendor_aliases is seeded with ~50 common aliases.

Revision ID: 037
Revises: 036
Create Date: 2026-05-21 00:00:04.000000
"""

# pylint: disable=no-member,invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hand-curated seed list. Keys are lowercase aliases as they appear in NVD/
# KEV/marketing copy; values are the canonical lowercase token used by the
# Month 3 matcher.
_SEED_ALIASES: list[tuple[str, str, str]] = [
    # canonical, alias, source
    ("microsoft", "microsoft corp", "manual"),
    ("microsoft", "microsoft corporation", "manual"),
    ("microsoft", "microsoft, inc.", "manual"),
    ("microsoft", "ms", "manual"),
    ("microsoft", "microsoft 365", "manual"),
    ("microsoft", "msft", "manual"),
    ("apple", "apple inc.", "manual"),
    ("apple", "apple computer, inc.", "manual"),
    ("google", "google llc", "manual"),
    ("google", "google inc.", "manual"),
    ("google", "alphabet inc.", "manual"),
    ("amazon", "amazon web services", "manual"),
    ("amazon", "aws", "manual"),
    ("amazon", "amazon.com", "manual"),
    ("amazon", "amazon.com, inc.", "manual"),
    ("oracle", "oracle corp", "manual"),
    ("oracle", "oracle corporation", "manual"),
    ("oracle", "sun microsystems", "manual"),
    ("adobe", "adobe systems", "manual"),
    ("adobe", "adobe inc.", "manual"),
    ("cisco", "cisco systems", "manual"),
    ("cisco", "cisco systems, inc.", "manual"),
    ("ibm", "international business machines", "manual"),
    ("ibm", "ibm corp", "manual"),
    ("vmware", "vmware, inc.", "manual"),
    ("vmware", "vmware inc", "manual"),
    ("redhat", "red hat", "manual"),
    ("redhat", "red hat, inc.", "manual"),
    ("apache", "apache software foundation", "manual"),
    ("apache", "the apache software foundation", "manual"),
    ("mozilla", "mozilla foundation", "manual"),
    ("mozilla", "mozilla corporation", "manual"),
    ("atlassian", "atlassian corp", "manual"),
    ("atlassian", "atlassian pty ltd", "manual"),
    ("github", "github, inc.", "manual"),
    ("gitlab", "gitlab inc.", "manual"),
    ("docker", "docker, inc.", "manual"),
    ("hashicorp", "hashicorp inc.", "manual"),
    ("elastic", "elasticsearch", "manual"),
    ("elastic", "elastic n.v.", "manual"),
    ("mongodb", "mongodb, inc.", "manual"),
    ("postgresql", "postgresql global development group", "manual"),
    ("postgresql", "postgres", "manual"),
    ("mysql", "mysql ab", "manual"),
    ("salesforce", "salesforce.com", "manual"),
    ("salesforce", "salesforce, inc.", "manual"),
    ("zoom", "zoom video communications", "manual"),
    ("slack", "slack technologies", "manual"),
    ("okta", "okta, inc.", "manual"),
    ("citrix", "citrix systems", "manual"),
    ("fortinet", "fortinet, inc.", "manual"),
    ("paloalto", "palo alto networks", "manual"),
    ("checkpoint", "check point software technologies", "manual"),
    ("juniper", "juniper networks", "manual"),
    ("nvidia", "nvidia corporation", "manual"),
]


def upgrade() -> None:
    """Apply migration."""
    op.create_table(
        "cpe_match_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vendor_normalized", sa.String(255), nullable=False),
        sa.Column("product_normalized", sa.String(255), nullable=False),
        sa.Column("version_normalized", sa.String(100), nullable=True),
        sa.Column("cpe_uri", sa.String(500), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vendor_normalized",
            "product_normalized",
            "version_normalized",
            name="uq_cpe_match_cache_vpv",
        ),
    )
    op.create_index(
        "ix_cpe_match_cache_vendor_product",
        "cpe_match_cache",
        ["vendor_normalized", "product_normalized"],
    )

    vendor_aliases = op.create_table(
        "vendor_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_vendor", sa.String(255), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias", name="uq_vendor_aliases_alias"),
    )
    op.create_index("ix_vendor_aliases_canonical", "vendor_aliases", ["canonical_vendor"])

    op.bulk_insert(
        vendor_aliases,
        [
            {"canonical_vendor": canonical, "alias": alias, "source": source}
            for canonical, alias, source in _SEED_ALIASES
        ],
    )


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("ix_vendor_aliases_canonical", table_name="vendor_aliases")
    op.drop_table("vendor_aliases")
    op.drop_index("ix_cpe_match_cache_vendor_product", table_name="cpe_match_cache")
    op.drop_table("cpe_match_cache")
