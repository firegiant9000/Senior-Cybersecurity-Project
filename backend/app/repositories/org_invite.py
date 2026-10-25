"""Repository abstraction for invitations and memberships."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from sqlalchemy import func, or_, select, update
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
        result = await self._session.execute(select(Invitation).where(Invitation.token == token))
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

    async def list_members(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[Membership], int]:
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

    async def lock_target_and_owners(
        self, org_id: int, user_id: int, caller_id: int
    ) -> tuple[Membership | None, int, Membership | None]:
        """Lock the target's and the caller's active memberships and the org's active owner rows,
        in id order.

        Returns the locked target and caller (None if not an active member) and the active owner
        count, all read under the lock so a concurrent role change or removal cannot slip between
        the checks and the write. One ordered statement keeps the lock order the same for every
        request, so concurrent requests queue instead of deadlocking. Held until commit.
        """
        result = await self._session.execute(
            select(Membership)
            .where(
                Membership.org_id == org_id,
                Membership.status == "active",
                or_(
                    Membership.role == "owner",
                    Membership.user_id == user_id,
                    Membership.user_id == caller_id,
                ),
            )
            .order_by(Membership.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        rows = list(result.scalars().all())
        target = next((m for m in rows if m.user_id == user_id), None)
        caller = next((m for m in rows if m.user_id == caller_id), None)
        owners = sum(1 for m in rows if m.role == "owner")
        return target, owners, caller

    async def update_member_role(
        self, membership: Membership, new_role: str, user: User | None = None
    ) -> Membership:
        """Change the membership role and mirror it to the legacy role, in ONE commit.

        The legacy role is only written when the user's legacy org is this org. If the commit
        fails, neither store changes.
        """
        membership.role = new_role
        if user is not None and user.org_id == membership.org_id:
            user.org_role = new_role
            self._session.add(user)
        await self._session.commit()
        await self._session.refresh(membership)
        return membership

    async def remove_member(self, membership: Membership, user: User | None) -> None:
        """Deactivate the membership, detach the user's legacy org and revoke the user's pending
        invites for this org, in ONE commit.

        The legacy fields are only cleared when they point at this org (a user whose legacy org
        is another one keeps it). If the commit fails, no store changes.
        """
        # Statements first: they autoflush, and the object changes should stay pending until
        # the single commit.
        await self._revoke_pending_invites(membership.org_id, membership.user_id, user)
        membership.status = "inactive"
        self._clear_legacy_org(user, membership.org_id)
        await self._session.commit()

    async def detach_legacy_member(self, user: User, org_id: int) -> None:
        """Remove a user whose access comes only from the legacy fields (no membership row)."""
        await self._revoke_pending_invites(org_id, user.id, user)
        self._clear_legacy_org(user, org_id)
        await self._session.commit()

    async def _revoke_pending_invites(self, org_id: int, user_id: int, user: User | None) -> None:
        """Revoke pending invites to the user's address and ones the user created (no commit)."""
        match = [Invitation.inviter_id == user_id]
        if user is not None and user.email:
            match.append(func.lower(Invitation.email) == user.email.lower())
        await self._session.execute(
            update(Invitation)
            .where(Invitation.org_id == org_id, Invitation.status == "pending", or_(*match))
            .values(status="revoked")
        )

    def _clear_legacy_org(self, user: User | None, org_id: int) -> None:
        if user is not None and user.org_id == org_id:
            user.org_id = None
            user.org_role = None
            self._session.add(user)

    async def has_membership_row(self, user_id: int, org_id: int) -> bool:
        """True if a membership row of any status exists for (user, org)."""
        result = await self._session.execute(
            select(func.count(Membership.id)).where(
                Membership.user_id == user_id, Membership.org_id == org_id
            )
        )
        return int(result.scalar_one()) > 0

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

    async def get_membership_for_update(self, user_id: int, org_id: int) -> Membership | None:
        """The (user, org) membership row in any status, locked. At most one row can exist."""
        result = await self._session.execute(
            select(Membership)
            .where(Membership.user_id == user_id, Membership.org_id == org_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def activate_membership(
        self, existing: Membership | None, user_id: int, org_id: int, role: str
    ) -> Membership:
        """Join the org with `role`: reactivate the (user, org) row `existing` (never keeping its
        old role) or insert a new one. Call inside the transaction that holds the invite lock."""
        if existing is None:
            return await self.create_membership(user_id, org_id, role)
        existing.role = role
        existing.status = "active"
        await self._session.flush()
        return existing

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
