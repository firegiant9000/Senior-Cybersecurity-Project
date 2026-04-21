"""Repository for NormalizationLog — fire-and-forget audit writes."""

import asyncio
import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.normalization_log import NormalizationLog

_log = logging.getLogger(__name__)


class SqlNormalizationLogRepository:
    """Writes normalization audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        *,
        data_type: str,
        raw_value: str,
        normalized_value: str,
        method: str,
        org_id: int | None = None,
        confidence: float = 1.0,
        created_by: int | None = None,
    ) -> NormalizationLog:
        row = NormalizationLog(
            org_id=org_id,
            data_type=data_type,
            raw_value=raw_value,
            normalized_value=normalized_value,
            confidence=confidence,
            method=method,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row


def get_normalization_log_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlNormalizationLogRepository:
    """Factory used as a dependency in the API layer."""
    return SqlNormalizationLogRepository(session)


# ---------------------------------------------------------------------------
# Fire-and-forget helper — creates its own session, swallows errors
# ---------------------------------------------------------------------------


async def _write_log_async(
    *,
    org_id: int | None,
    data_type: str,
    raw_value: str,
    normalized_value: str,
    method: str,
    confidence: float,
    created_by: int | None,
) -> None:
    from app.db.engine import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            row = NormalizationLog(
                org_id=org_id,
                data_type=data_type,
                raw_value=raw_value,
                normalized_value=normalized_value,
                confidence=confidence,
                method=method,
                created_by=created_by,
            )
            session.add(row)
            await session.commit()
    except Exception:
        _log.debug("normalization log write failed", exc_info=True)


def fire_and_forget_normalization_log(
    *,
    org_id: int | None,
    data_type: str,
    raw_value: str,
    normalized_value: str,
    method: str,
    confidence: float = 1.0,
    created_by: int | None = None,
) -> None:
    """Schedule a normalization log write as a background asyncio task.

    Does not block the caller. Errors are suppressed — audit log writes
    must never affect the user-facing response.
    """
    asyncio.create_task(
        _write_log_async(
            org_id=org_id,
            data_type=data_type,
            raw_value=raw_value,
            normalized_value=normalized_value,
            method=method,
            confidence=confidence,
            created_by=created_by,
        )
    )
