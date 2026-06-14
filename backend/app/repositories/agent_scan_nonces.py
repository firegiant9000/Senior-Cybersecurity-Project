"""Repository abstraction for AgentScanNonces (Month 4 Phase 3 — replay guard)."""

# pylint: disable=too-few-public-methods

import logging
from datetime import datetime

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.agent_scan_nonce import AgentScanNonce
from app.db.engine import get_session

logger = logging.getLogger(__name__)


class SqlAgentScanNonceRepository:
    """Records and queries agent-scan replay markers.

    Reads are not org-scoped: the ``(scan_id, nonce)`` pair is globally unique
    and the org is already pinned by the authenticated enrollment. Scoping the
    lookup by org would let a replay slip through if it claimed a different org.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seen_within(self, scan_id: str, nonce: str, since: datetime) -> bool:
        """True if this ``(scan_id, nonce)`` was recorded at/after ``since``."""
        result = await self._session.execute(
            select(AgentScanNonce.id).where(
                AgentScanNonce.scan_id == scan_id,
                AgentScanNonce.nonce == nonce,
                AgentScanNonce.seen_at >= since,
            )
        )
        return result.first() is not None

    async def record(
        self,
        *,
        org_id: int,
        agent_enrollment_id: int | None,
        scan_id: str,
        nonce: str,
    ) -> AgentScanNonce:
        """Persist a replay marker. May raise ``IntegrityError`` on the unique
        ``(scan_id, nonce)`` constraint — the caller treats that as a replay."""
        row = AgentScanNonce(
            org_id=org_id,
            agent_enrollment_id=agent_enrollment_id,
            scan_id=scan_id,
            nonce=nonce,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def purge_before(self, cutoff: datetime) -> int:
        """Delete markers older than ``cutoff``; returns rows removed.

        Keeps the table bounded — once a row is older than the replay window it
        can never cause a rejection, so it is safe to drop.
        """
        result = await self._session.execute(
            delete(AgentScanNonce).where(AgentScanNonce.seen_at < cutoff)
        )
        return result.rowcount or 0


def get_agent_scan_nonce_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAgentScanNonceRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAgentScanNonceRepository(session)
