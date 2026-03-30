"""Repository abstraction for OrgUploads."""

# pylint: disable=too-few-public-methods,duplicate-code

import logging

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.org_upload import OrgUpload

logger = logging.getLogger(__name__)


class SqlOrgUploadRepository:
    """Queries OrgUploads from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        org_id: int,
        uploaded_by: int | None,
        original_filename: str,
        stored_filename: str,
        file_size_bytes: int,
        content_type: str,
        upload_purpose: str | None = None,
    ) -> OrgUpload:
        upload = OrgUpload(
            org_id=org_id,
            uploaded_by=uploaded_by,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size_bytes=file_size_bytes,
            content_type=content_type,
            upload_purpose=upload_purpose,
        )
        self._session.add(upload)
        await self._session.commit()
        await self._session.refresh(upload)
        return upload

    async def get_by_id(self, upload_id: int, org_id: int) -> OrgUpload | None:
        result = await self._session.execute(
            select(OrgUpload).where(OrgUpload.id == upload_id, OrgUpload.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_uploads(
        self, org_id: int, page: int, page_size: int
    ) -> tuple[list[OrgUpload], int]:
        stmt = (
            select(OrgUpload)
            .where(OrgUpload.org_id == org_id)
            .order_by(OrgUpload.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self._session.execute(
            select(func.count(OrgUpload.id)).where(OrgUpload.org_id == org_id)
        )
        total = int(total_result.scalar_one())

        return rows, total

    async def delete(self, upload_id: int, org_id: int) -> OrgUpload | None:
        """Delete an upload record and return it (caller handles file removal)."""
        upload = await self.get_by_id(upload_id, org_id)
        if upload is None:
            return None
        await self._session.delete(upload)
        await self._session.commit()
        return upload


def get_upload_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlOrgUploadRepository:
    """Factory used as a dependency in the API layer."""
    return SqlOrgUploadRepository(session)
