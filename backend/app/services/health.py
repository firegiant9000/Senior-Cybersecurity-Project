"""Database reachability check for ``/health``."""

import asyncio
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_lock = asyncio.Lock()
# (checked_at on time.monotonic(), ok); None until the first check completes.
_cache: tuple[float, bool] | None = None


async def _select_one(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def database_reachable(db_engine: AsyncEngine, *, timeout: float) -> bool:
    """True if ``SELECT 1`` succeeds within ``timeout`` seconds.

    Any exception or timeout means unreachable. Only the exception type is
    logged, never its text (it can carry the host or credentials).
    """
    try:
        await asyncio.wait_for(_select_one(db_engine), timeout)
    except Exception as exc:  # noqa: BLE001 - any failure (incl. TimeoutError) means unreachable
        logger.warning("health: database unreachable (%s)", type(exc).__name__)
        return False
    return True


def _fresh() -> bool | None:
    if _cache is None:
        return None
    checked_at, ok = _cache
    if time.monotonic() - checked_at < settings.HEALTH_CACHE_SECONDS:
        return ok
    return None


async def cached_database_reachable(db_engine: AsyncEngine) -> bool:
    """Single-flight, short-lived cached ``database_reachable``.

    Concurrent callers share one query. The timestamp is taken after the
    check completes, and each caller re-reads the cache once it holds the lock,
    so a slow check serves everyone queued behind it.
    """
    global _cache
    async with _lock:
        cached = _fresh()
        if cached is not None:
            return cached
        ok = await database_reachable(db_engine, timeout=settings.HEALTH_DB_TIMEOUT_SECONDS)
        _cache = (time.monotonic(), ok)
        return ok


def reset_cache() -> None:
    """Clear the cached result (tests only)."""
    global _cache
    _cache = None
