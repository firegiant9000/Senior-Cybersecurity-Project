"""Alembic environment configuration."""

# pylint: disable=no-member,wrong-import-position

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    create_engine,
    pool,
)

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import app.db.invitation  # noqa: E402, F401  # register Invitation with Base.metadata
import app.db.membership  # noqa: E402, F401  # register Membership with Base.metadata
import app.db.models  # noqa: E402, F401  # register ORM models with Base.metadata
import app.db.normalization_log  # noqa: E402, F401  # register NormalizationLog with Base.metadata
import app.db.org_domain  # noqa: E402, F401  # register OrgDomain with Base.metadata
import app.db.org_upload  # noqa: E402, F401  # register OrgUpload with Base.metadata
import app.db.org_vendor  # noqa: E402, F401  # register OrgVendor with Base.metadata
import app.db.organization  # noqa: E402, F401  # register Organization with Base.metadata
import app.db.technology_vendor  # noqa: E402, F401  # register TechnologyVendor with Base.metadata
import app.db.user  # noqa: E402, F401  # register User (with org FK) with Base.metadata
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# this is the Alembic Config object
config = context.config

# Alembic requires a sync driver; swap asyncpg → psycopg for migrations
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
config.set_main_option("sqlalchemy.url", sync_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    def process_revision_directives(_context, _revision, directives):
        if config.cmd_opts is not None and config.cmd_opts.autogenerate:
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []

    url = config.get_main_option("sqlalchemy.url")
    if url is None:
        raise ValueError("sqlalchemy.url is not set in Alembic config")
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
