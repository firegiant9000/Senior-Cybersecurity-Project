"""Database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger(__name__)


def _import_all_orm_models() -> None:
    """Import every module that registers a model on ``Base.metadata``.

    Ensures ``create_all`` sees the full schema regardless of import order.
    """
    import app.db.models  # noqa: F401
    import app.db.org_domain  # noqa: F401
    import app.db.org_upload  # noqa: F401
    import app.db.org_vendor  # noqa: F401
    import app.db.organization  # noqa: F401
    import app.db.technology_vendor  # noqa: F401
    import app.db.org_invite  # noqa: F401
    import app.db.user  # noqa: F401


def _ensure_organization_profile_columns(connection: Connection) -> None:
    """Add ``logo_url`` / ``primary_domain`` when upgrading an existing DB.

    ``Base.metadata.create_all()`` creates new tables but does **not** add columns
    to tables that already exist. This keeps ``init_db()`` usable without Alembic.
    """
    inspector = inspect(connection)
    if not inspector.has_table("organizations"):
        return
    existing = {col["name"].lower() for col in inspector.get_columns("organizations")}
    if "logo_url" not in existing:
        connection.execute(text("ALTER TABLE organizations ADD COLUMN logo_url VARCHAR(500)"))
        logger.info("Added column organizations.logo_url")
    if "primary_domain" not in existing:
        connection.execute(
            text("ALTER TABLE organizations ADD COLUMN primary_domain VARCHAR(255)"),
        )
        logger.info("Added column organizations.primary_domain")


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    future=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:  # type: ignore[reportGeneralTypeIssues]
        yield session


async def init_db() -> None:
    """Initialize database: create missing tables and align known schema drifts."""
    _import_all_orm_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_organization_profile_columns)
    logger.info("Database initialized")


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()
    logger.info("Database connection closed")
