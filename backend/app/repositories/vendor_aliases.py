"""Repository abstraction for VendorAliases.

Vendor aliases are global (not org-scoped) since they describe upstream
naming conventions from NVD / KEV / vendor marketing copy.
"""

# pylint: disable=too-few-public-methods

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.vendor_alias import VendorAlias
from app.schemas.vendor_alias import VendorAliasCreate

logger = logging.getLogger(__name__)


class SqlVendorAliasRepository:
    """Queries VendorAliases from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: VendorAliasCreate) -> VendorAlias:
        row = VendorAlias(**data.model_dump())
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def resolve(self, alias: str) -> str:
        """Return the canonical vendor token for ``alias`` (case-insensitive).

        Falls back to the input (lowercased, stripped) when no alias is
        registered, so callers can use the result as a normalized matcher key.
        """
        normalized = alias.strip().lower()
        result = await self._session.execute(
            select(VendorAlias.canonical_vendor).where(
                func.lower(VendorAlias.alias) == normalized
            )
        )
        canonical = result.scalar_one_or_none()
        return canonical if canonical is not None else normalized

    async def list_all(self) -> list[VendorAlias]:
        result = await self._session.execute(
            select(VendorAlias).order_by(
                VendorAlias.canonical_vendor, VendorAlias.alias
            )
        )
        return list(result.scalars().all())

    async def list_for_canonical(self, canonical_vendor: str) -> list[VendorAlias]:
        result = await self._session.execute(
            select(VendorAlias)
            .where(func.lower(VendorAlias.canonical_vendor) == canonical_vendor.lower())
            .order_by(VendorAlias.alias)
        )
        return list(result.scalars().all())


def get_vendor_alias_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlVendorAliasRepository:
    """Factory used as a dependency in the API layer."""
    return SqlVendorAliasRepository(session)
