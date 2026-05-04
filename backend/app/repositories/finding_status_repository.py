"""Repository for FindingStatus rows — per-org remediation state for findings."""

# pylint: disable=too-few-public-methods

import logging

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.finding_status import FindingStatus

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {"open", "done", "dismissed"}


class SqlFindingStatusRepository:
    """Reads and writes finding_statuses scoped to a single org."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def map_for_org(self, org_id: int) -> dict[str, str]:
        """Return ``{stable_key: status}`` for the given org."""
        result = await self._session.execute(
            select(FindingStatus.stable_key, FindingStatus.status).where(
                FindingStatus.org_id == org_id
            )
        )
        return {row[0]: row[1] for row in result.all()}

    async def list_for_org(self, org_id: int) -> list[FindingStatus]:
        result = await self._session.execute(
            select(FindingStatus).where(FindingStatus.org_id == org_id)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        org_id: int,
        stable_key: str,
        status: str,
        updated_by: int | None,
        title: str | None = None,
        severity: str | None = None,
    ) -> FindingStatus:
        """Idempotent upsert by ``(org_id, stable_key)``.

        ``status='open'`` collapses to a delete so the table only carries
        rows that actually diverge from default. Keeps the join cheap and
        avoids leaking stale rows for findings the user has reverted.

        ``title`` and ``severity`` are denormalized from the finding the
        user clicked on, so the risk-score credit can be computed without
        joining back through the latest findings_snapshot.
        """
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {status}")

        if status == "open":
            await self._session.execute(
                FindingStatus.__table__.delete().where(
                    FindingStatus.org_id == org_id,
                    FindingStatus.stable_key == stable_key,
                )
            )
            await self._session.commit()
            placeholder = FindingStatus(
                org_id=org_id,
                stable_key=stable_key,
                status="open",
                updated_by=updated_by,
                title=title,
                severity=severity,
            )
            return placeholder

        stmt = (
            pg_insert(FindingStatus)
            .values(
                org_id=org_id,
                stable_key=stable_key,
                status=status,
                updated_by=updated_by,
                title=title,
                severity=severity,
            )
            .on_conflict_do_update(
                constraint="uq_finding_status_org_key",
                set_={
                    "status": status,
                    "updated_by": updated_by,
                    "title": title,
                    "severity": severity,
                },
            )
            .returning(FindingStatus.id)
        )
        result = await self._session.execute(stmt)
        new_id = result.scalar_one()
        await self._session.commit()

        row = await self._session.execute(select(FindingStatus).where(FindingStatus.id == new_id))
        return row.scalar_one()


def get_finding_status_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlFindingStatusRepository:
    """FastAPI dependency factory."""
    return SqlFindingStatusRepository(session)
