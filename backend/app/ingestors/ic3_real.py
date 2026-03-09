"""IC3 real-data ingestion adapter.

This module provides the ``ingest_ic3_real`` function used by
``scripts/ingest_real_data.py``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


async def ingest_ic3_real(
    _session: AsyncSession,
    *,
    years: Sequence[int] | None = None,
    use_pdf: bool = True,
) -> int:
    """Ingest IC3 data using the enhanced PDF ingestor.

    Args:
        session: Active database session from the caller.
        years: Optional sequence of years to ingest.
        use_pdf: Whether to use the PDF-based real-data ingestion flow.

    Returns:
        Number of records ingested.
    """
    if not use_pdf:
        logger.info("IC3 fallback mode requested; skipping PDF ingestion")
        return 0

    try:
        from scripts.ingest_ic3_enhanced import ingest_ic3_real_data
    except ImportError as exc:  # pragma: no cover
        logger.error("Unable to import IC3 enhanced ingestor: %s", exc)
        return 0

    normalized_years = list(years) if years is not None else None
    return await ingest_ic3_real_data(
        db_url=settings.DATABASE_URL,
        years=normalized_years,
    )
