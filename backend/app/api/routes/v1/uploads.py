"""Upload routes — file upload management for organizations."""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.user import User
from app.repositories.org_upload import SqlOrgUploadRepository, get_upload_repo
from app.schemas.org_upload import OrgUploadListResponse, OrgUploadRead
from app.services.file_upload import delete_upload_file, get_upload_path, save_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/organizations/{org_id}/uploads", response_model=OrgUploadRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def upload_file(
    request: Request,  # noqa: ARG001
    org_id: int,
    file: UploadFile,
    purpose: Annotated[str | None, Query(max_length=100)] = None,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgUploadRepository = Depends(get_upload_repo),
    session: AsyncSession = Depends(get_session),
):
    """Upload a file for the organization."""
    await check_org_access(current_user, org_id, session)

    original, stored, size = await save_upload(org_id, file)

    try:
        upload = await repo.create(
            org_id=org_id,
            uploaded_by=current_user.id,
            original_filename=original,
            stored_filename=stored,
            file_size_bytes=size,
            content_type=file.content_type or "application/octet-stream",
            upload_purpose=purpose,
        )
    except SQLAlchemyError:
        # Clean up the file if DB insert fails
        delete_upload_file(org_id, stored)
        logger.exception("Failed to save upload record for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to save upload")
    return upload


@router.get("/organizations/{org_id}/uploads", response_model=OrgUploadListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_uploads(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgUploadRepository = Depends(get_upload_repo),
    session: AsyncSession = Depends(get_session),
):
    """List uploads for an organization (paginated)."""
    await check_org_access(current_user, org_id, session)
    try:
        items, total = await repo.list_uploads(org_id, page, page_size)
    except SQLAlchemyError:
        logger.exception("Failed to list uploads for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to list uploads")
    return OrgUploadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[OrgUploadRead.model_validate(u) for u in items],
    )


@router.delete("/organizations/{org_id}/uploads/{upload_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def delete_upload(
    request: Request,  # noqa: ARG001
    org_id: int,
    upload_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgUploadRepository = Depends(get_upload_repo),
    session: AsyncSession = Depends(get_session),
):
    """Delete an uploaded file and its record."""
    await check_org_access(current_user, org_id, session)
    try:
        upload = await repo.delete(upload_id, org_id)
    except SQLAlchemyError:
        logger.exception("Failed to delete upload %s", upload_id)
        raise HTTPException(status_code=500, detail="Failed to delete upload")
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    delete_upload_file(org_id, upload.stored_filename)
    return None


@router.get("/organizations/{org_id}/uploads/{upload_id}/download")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def download_upload(
    request: Request,  # noqa: ARG001
    org_id: int,
    upload_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgUploadRepository = Depends(get_upload_repo),
    session: AsyncSession = Depends(get_session),
):
    """Download a previously uploaded file."""
    await check_org_access(current_user, org_id, session)
    try:
        upload = await repo.get_by_id(upload_id, org_id)
    except SQLAlchemyError:
        logger.exception("Failed to fetch upload %s", upload_id)
        raise HTTPException(status_code=500, detail="Failed to fetch upload")
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    path = get_upload_path(org_id, upload.stored_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=path,
        filename=upload.original_filename,
        media_type=upload.content_type,
    )
