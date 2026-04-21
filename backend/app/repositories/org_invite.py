"""Repository abstraction for invitations and memberships."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.user import User

logger = logging.getLogger(__name__)

INVITE_TTL_HOURS = 72


class SqlOrgInviteRepository:
    """Queries invitations and memberships from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        org_id: int,
        invited_email: str,
        org_role: str,
        invited_by: int | None,
    ) -> Invitation:
        token = secrets.token_urlsafe(32)
        invite = Invitation(
            org_id=org_id,
            email=invited_email.lower(),
            token=token,
            role=org_role,
            status="pending",
            inviter_id=invited_by,
            expires_at=datetime.now(UTC) + timedelta(hours=INVITE_TTL_HOURS),
        )
        self._session.add(invite)
        await self._session.commit()
        await self._session.refresh(invite)
        return invite

    async def get_by_token(self, token: str) -> Invitation | None:
        result = await self._session.execute(
            select(Invitation).where(Invitation.token == token)
        )
        return result.scalar_one_or_none()

    async def get_by_token_for_update(self, token: str) -> Invitation | None:
        result = await self._session.execute(
            select(Invitation).where(Invitation.token == token).with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[Invitation], int]:
        stmt = (
            select(Invitation)
            .where(Invitation.org_id == org_id)
            .order_by(Invitation.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(Invitation.id)).where(Invitation.org_id == org_id)
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def revoke(self, invite_id: int, org_id: int) -> bool:
        result = await self._session.execute(
            update(Invitation)
            .where(
                Invitation.id == invite_id,
                Invitation.org_id == org_id,
                Invitation.status == "pending",
            )
            .values(status="revoked")
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0

    async def mark_accepted(self, invite: Invitation) -> None:
        invite.status = "accepted"
        self._session.add(invite)

    async def expire_stale(self) -> int:
        """Mark pending invites past their expiration as expired."""
        result = await self._session.execute(
            update(Invitation)
            .where(
                Invitation.status == "pending",
                Invitation.expires_at < datetime.now(UTC),
            )
            .values(status="expired")
        )
        await self._session.commit()
        return result.rowcount or 0

    # ── Member queries ────────────────────────────────────────────────────

    async def list_members(self, org_id: int, page: int, page_size: int) -> tuple[list[Membership], int]:
        stmt = (
            select(Membership)
            .where(Membership.org_id == org_id, Membership.status == "active")
            .order_by(Membership.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(Membership.id)).where(
                Membership.org_id == org_id,
                Membership.status == "active",
            )
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def list_members_with_users(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[tuple[Membership, User]], int]:
        stmt = (
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, Membership.status == "active")
            .order_by(User.email.asc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.all())
        total_result = await self._session.execute(
            select(func.count(Membership.id)).where(
                Membership.org_id == org_id,
                Membership.status == "active",
            )
        )
        total = int(total_result.scalar_one())
        return rows, total

    async def get_member(self, user_id: int, org_id: int) -> Membership | None:
        result = await self._session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.org_id == org_id,
                Membership.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def update_member_role(self, membership: Membership, new_role: str) -> Membership:
        membership.role = new_role
        await self._session.commit()
        await self._session.refresh(membership)
        return membership

    async def remove_member(self, membership: Membership) -> None:
        membership.status = "inactive"
        await self._session.commit()

    async def count_active_owners(self, org_id: int) -> int:
        result = await self._session.execute(
            select(func.count(Membership.id)).where(
                Membership.org_id == org_id,
                Membership.status == "active",
                Membership.role == "owner",
            )
        )
        return int(result.scalar_one())

    async def get_user(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_active_membership(self, user_id: int, org_id: int) -> Membership | None:
        result = await self._session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.org_id == org_id,
                Membership.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def create_membership(self, user_id: int, org_id: int, role: str) -> Membership:
        membership = Membership(
            user_id=user_id,
            org_id=org_id,
            role=role,
            status="active",
        )
        self._session.add(membership)
        await self._session.flush()
        return membership

    async def get_active_membership_by_email(self, org_id: int, email: str) -> Membership | None:
        result = await self._session.execute(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.org_id == org_id,
                Membership.status == "active",
                func.lower(User.email) == email.lower(),
            )
        )
        return result.scalar_one_or_none()


def get_invite_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgInviteRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgInviteRepository(session)
