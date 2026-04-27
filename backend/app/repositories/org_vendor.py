"""Repository abstraction for OrgVendors."""

# pylint: disable=too-few-public-methods,duplicate-code

import logging

from fastapi import Depends
from sqlalchemy import case, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import KEV
from app.db.org_vendor import OrgVendor
from app.schemas.org_vendor import OrgVendorCreate, OrgVendorRead, OrgVendorUpdate
from app.services.vendor_matching import VENDOR_ALIASES

logger = logging.getLogger(__name__)


class SqlOrgVendorRepository:
    """Queries OrgVendors from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: int, data: OrgVendorCreate) -> OrgVendor:
        vendor = OrgVendor(org_id=org_id, **data.model_dump())
        self._session.add(vendor)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def create_or_get(self, org_id: int, data: OrgVendorCreate) -> tuple[OrgVendor, bool]:
        """Insert a vendor if (org, vendor, product) doesn't exist; otherwise
        return the existing row.

        Returns (vendor, created). Used by routes that need idempotent
        behavior (e.g. cloud-provider sync from the security profile).
        """
        payload = data.model_dump()
        vendor_name = payload["vendor_name"]
        product_name = payload.get("product_name", "") or ""

        stmt = (
            pg_insert(OrgVendor)
            .values(org_id=org_id, vendor_name=vendor_name, product_name=product_name)
            .on_conflict_do_nothing(constraint="uq_org_vendor_product")
            .returning(OrgVendor.id)
        )
        result = await self._session.execute(stmt)
        new_id = result.scalar_one_or_none()
        await self._session.commit()

        if new_id is not None:
            vendor = await self.get_by_id(new_id, org_id)
            assert vendor is not None
            return vendor, True

        existing = await self._session.execute(
            select(OrgVendor).where(
                OrgVendor.org_id == org_id,
                OrgVendor.vendor_name == vendor_name,
                OrgVendor.product_name == product_name,
            )
        )
        return existing.scalar_one(), False

    async def get_by_id(self, vendor_id: int, org_id: int) -> OrgVendor | None:
        result = await self._session.execute(
            select(OrgVendor).where(OrgVendor.id == vendor_id, OrgVendor.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_vendors(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[OrgVendorRead], int]:
        # Subquery: count KEV entries matching each vendor name. Uses the
        # shared VENDOR_ALIASES map so cloud/SaaS display names (AWS,
        # Microsoft 365, GCP, ...) get the same KEV count the alerts
        # endpoint would surface.
        canonical_vendor = case(
            *[
                (func.lower(OrgVendor.vendor_name) == alias, literal(canonical.lower()))
                for alias, canonical in VENDOR_ALIASES.items()
            ],
            else_=func.lower(OrgVendor.vendor_name),
        )
        kev_count = (
            select(func.count(KEV.id))
            .where(func.lower(KEV.vendor) == canonical_vendor)
            .correlate(OrgVendor)
            .scalar_subquery()
        )

        stmt = (
            select(OrgVendor, kev_count.label("matched_kev_count"))
            .where(OrgVendor.org_id == org_id)
            .order_by(OrgVendor.vendor_name, OrgVendor.product_name)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows: list[OrgVendorRead] = []
        for vendor, kev_cnt in result.all():
            read = OrgVendorRead.model_validate(vendor)
            read.matched_kev_count = kev_cnt or 0
            rows.append(read)

        total_result = await self._session.execute(
            select(func.count(OrgVendor.id)).where(OrgVendor.org_id == org_id)
        )
        total = int(total_result.scalar_one())

        return rows, total

    async def update(self, vendor_id: int, org_id: int, data: OrgVendorUpdate) -> OrgVendor | None:
        vendor = await self.get_by_id(vendor_id, org_id)
        if vendor is None:
            return None
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(vendor, field, value)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def delete(self, vendor_id: int, org_id: int) -> bool:
        vendor = await self.get_by_id(vendor_id, org_id)
        if vendor is None:
            return False
        await self._session.delete(vendor)
        await self._session.commit()
        return True

    async def bulk_import(self, org_id: int, rows: list[dict[str, str]]) -> tuple[int, int]:
        """Import vendors in bulk, skipping duplicates.

        Returns (imported_count, skipped_count).
        """
        imported = 0
        skipped = 0
        for row in rows:
            stmt = (
                pg_insert(OrgVendor)
                .values(
                    org_id=org_id,
                    vendor_name=row["vendor_name"],
                    product_name=row.get("product_name", ""),
                )
                .on_conflict_do_nothing(constraint="uq_org_vendor_product")
            )
            result = await self._session.execute(stmt)
            if result.rowcount:  # type: ignore[union-attr]
                imported += 1
            else:
                skipped += 1
        await self._session.commit()
        return imported, skipped


def get_vendor_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgVendorRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgVendorRepository(session)
