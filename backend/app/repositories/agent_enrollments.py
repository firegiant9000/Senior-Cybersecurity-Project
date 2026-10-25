"""Repository abstraction for AgentEnrollments (Month 4 Phase 1)."""

# pylint: disable=too-few-public-methods

import logging
from datetime import datetime

from fastapi import Depends
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.db.agent_enrollment import AgentEnrollment
from app.db.engine import get_session

logger = logging.getLogger(__name__)


class SqlAgentEnrollmentRepository:
    """Queries AgentEnrollments. Reads are org-scoped except ``get_by_prefix``.

    ``get_by_prefix`` is intentionally *not* org-scoped: token verification only
    has the bearer token, and the org is *derived* from the resolved row. Every
    other read takes an ``org_id`` so an admin can only see/manage their own
    org's agents.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        org_id: int,
        *,
        name: str,
        token_hash: str,
        token_prefix: str,
        scopes: list[str] | None,
        created_by_user_id: int | None,
        expires_at: datetime | None,
        chain_root_id: int | None = None,
    ) -> AgentEnrollment:
        enrollment = AgentEnrollment(
            chain_root_id=chain_root_id,
            org_id=org_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self._session.add(enrollment)
        await self._session.commit()
        await self._session.refresh(enrollment)
        return enrollment

    async def get_by_prefix(self, token_prefix: str) -> AgentEnrollment | None:
        """Resolve a token's enrollment by its public prefix (NOT org-scoped)."""
        result = await self._session.execute(
            select(AgentEnrollment).where(AgentEnrollment.token_prefix == token_prefix)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, enrollment_id: int, org_id: int) -> AgentEnrollment | None:
        result = await self._session.execute(
            select(AgentEnrollment).where(
                AgentEnrollment.id == enrollment_id,
                AgentEnrollment.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, org_id: int) -> list[AgentEnrollment]:
        stmt = (
            select(AgentEnrollment)
            .where(AgentEnrollment.org_id == org_id)
            .order_by(AgentEnrollment.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def touch_last_used(self, enrollment: AgentEnrollment, when: datetime) -> None:
        enrollment.last_used_at = when
        await self._session.commit()

    async def _lock_chain_root(self, root_id: int) -> None:
        """Lock the chain's root row so chain writers serialize.

        ``FOR NO KEY UPDATE`` (not ``FOR UPDATE``): it doesn't conflict with the ``KEY SHARE``
        lock an in-flight agent upload holds on its enrollment row, but still conflicts with
        itself, so rotate/revoke and revoke/revoke wait for each other. Held until commit.
        """
        await self._session.execute(
            select(AgentEnrollment.id)
            .where(AgentEnrollment.id == root_id)
            .with_for_update(key_share=True)
        )

    async def claim_for_rotation(
        self, enrollment: AgentEnrollment, *, grace_until: datetime, now: datetime
    ) -> bool:
        """Start the predecessor's grace window, only if the row is still active in the database.

        One conditional UPDATE after the chain-root lock: a concurrent rotation or revoke that
        got there first leaves 0 rows matched, so a stale in-memory object can't win. Does NOT
        commit: the caller's successor INSERT commits the claim and the new row together.
        Returns whether the claim matched a row.
        """
        await self._lock_chain_root(enrollment.chain_root_id or enrollment.id)
        result = await self._session.execute(
            update(AgentEnrollment)
            .where(
                AgentEnrollment.id == enrollment.id,
                AgentEnrollment.revoked_at.is_(None),
                or_(AgentEnrollment.expires_at.is_(None), AgentEnrollment.expires_at > now),
            )
            .values(revoked_at=grace_until)
            .returning(AgentEnrollment.id)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is None:
            return False
        # Mirror the UPDATE in memory without marking the attribute dirty (no second write).
        set_committed_value(enrollment, "revoked_at", grace_until)
        return True

    async def end_grace(self, enrollment: AgentEnrollment, *, when: datetime) -> bool:
        """End this one row's grace window at ``when``; no other row of the chain changes.

        Takes the chain-root lock, then one conditional UPDATE that matches only while the row's
        ``revoked_at`` is still in the future and the row has not expired, so it can only move
        that time earlier, never later,
        and a concurrent revoke or end-grace that got there first leaves 0 rows matched.
        Returns whether a row changed.
        """
        await self._lock_chain_root(enrollment.chain_root_id or enrollment.id)
        result = await self._session.execute(
            update(AgentEnrollment)
            .where(
                AgentEnrollment.id == enrollment.id,
                AgentEnrollment.org_id == enrollment.org_id,
                AgentEnrollment.revoked_at > when,
                or_(AgentEnrollment.expires_at.is_(None), AgentEnrollment.expires_at > when),
            )
            .values(revoked_at=when)
            .returning(AgentEnrollment.id)
            .execution_options(synchronize_session=False)
        )
        changed = result.scalar_one_or_none() is not None
        await self._session.commit()
        await self._session.refresh(enrollment)
        return changed

    async def revoke_chain(self, enrollment: AgentEnrollment, *, when: datetime) -> list[int]:
        """Revoke every row of the enrollment's chain at ``when``; never moves a time later.

        Locks the root first, so a rotation still inserting its successor commits before the
        UPDATE starts (and its snapshot includes the successor). Returns the ids changed.
        """
        root = enrollment.chain_root_id or enrollment.id
        await self._lock_chain_root(root)
        result = await self._session.execute(
            update(AgentEnrollment)
            .where(
                AgentEnrollment.org_id == enrollment.org_id,
                or_(AgentEnrollment.id == root, AgentEnrollment.chain_root_id == root),
                or_(AgentEnrollment.revoked_at.is_(None), AgentEnrollment.revoked_at > when),
            )
            .values(revoked_at=when)
            .returning(AgentEnrollment.id)
            .execution_options(synchronize_session=False)
        )
        changed = sorted(result.scalars().all())
        await self._session.commit()
        await self._session.refresh(enrollment)
        return changed


def get_agent_enrollment_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAgentEnrollmentRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAgentEnrollmentRepository(session)
