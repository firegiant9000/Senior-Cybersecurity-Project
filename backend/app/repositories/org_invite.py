"""Repository abstraction for OrgInvites and org member queries."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.org_invite import OrgInvite
from app.db.user import User

logger = logging.getLogger(__name__)

INVITE_TTL_HOURS = 72


class SqlOrgInviteRepository:
    """Queries OrgInvites from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        org_id: int,
        invited_email: str,
        org_role: str,
        invited_by: int | None,
    ) -> OrgInvite:
        token = secrets.token_urlsafe(32)
        invite = OrgInvite(
            org_id=org_id,
            invited_email=invited_email.lower(),
            invite_token=token,
            org_role=org_role,
            status="pending",
            invited_by=invited_by,
            expires_at=datetime.now(UTC) + timedelta(hours=INVITE_TTL_HOURS),
        )
        self._session.add(invite)
        await self._session.commit()
        await self._session.refresh(invite)
        return invite

    async def get_by_token(self, token: str) -> OrgInvite | None:
        result = await self._session.execute(
            select(OrgInvite).where(OrgInvite.invite_token == token)
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[OrgInvite], int]:
        stmt = (
            select(OrgInvite)
            .where(OrgInvite.org_id == org_id)
            .order_by(OrgInvite.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(OrgInvite.id)).where(OrgInvite.org_id == org_id)
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def revoke(self, invite_id: int, org_id: int) -> bool:
        result = await self._session.execute(
            update(OrgInvite)
            .where(
                OrgInvite.id == invite_id,
                OrgInvite.org_id == org_id,
                OrgInvite.status == "pending",
            )
            .values(status="revoked")
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0

    async def mark_accepted(self, invite: OrgInvite) -> None:
        invite.status = "accepted"
        await self._session.commit()

    async def expire_stale(self) -> int:
        """Mark pending invites past their expiration as expired."""
        result = await self._session.execute(
            update(OrgInvite)
            .where(
                OrgInvite.status == "pending",
                OrgInvite.expires_at < datetime.now(UTC),
            )
            .values(status="expired")
        )
        await self._session.commit()
        return result.rowcount or 0

    # ── Member queries ────────────────────────────────────────────────────

    async def list_members(self, org_id: int, page: int, page_size: int) -> tuple[list[User], int]:
        stmt = (
            select(User)
            .where(User.org_id == org_id)
            .order_by(User.email)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(User.id)).where(User.org_id == org_id)
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def get_member(self, user_id: int, org_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def update_member_role(self, user: User, new_role: str) -> User:
        user.org_role = new_role
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def remove_member(self, user: User) -> None:
        user.org_id = None
        user.org_role = None
        await self._session.commit()


def get_invite_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgInviteRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgInviteRepository(session)
