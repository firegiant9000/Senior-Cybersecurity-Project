"""Vendor routes — org technology stack management + KEV autocomplete."""

import csv
import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.engine import get_session
from app.db.models import KEV
from app.db.organization import Organization
from app.db.user import User
from app.repositories.org_vendor import SqlOrgVendorRepository, get_vendor_repo
from app.schemas.org_vendor import (
    OrgVendorCreate,
    OrgVendorImportResponse,
    OrgVendorListResponse,
    OrgVendorRead,
    OrgVendorUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CSV_ROWS = 500


def _parse_csv_rows(
    reader: csv.DictReader,  # type: ignore[type-arg]
) -> tuple[list[dict[str, str]], list[str]]:
    """Validate and extract rows from a CSV DictReader.

    Returns (valid_rows, errors).
    """
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):  # row 1 is header
        if len(rows) >= MAX_CSV_ROWS:
            errors.append(
                f"Row {i}: exceeded maximum of {MAX_CSV_ROWS} rows — remaining rows skipped"
            )
            break
        vendor_name = (row.get("vendor_name") or "").strip()
        if not vendor_name:
            errors.append(f"Row {i}: missing vendor_name")
            continue
        if len(vendor_name) > 255:
            errors.append(f"Row {i}: vendor_name exceeds 255 characters")
            continue
        product_name = (row.get("product_name") or "").strip()
        if len(product_name) > 255:
            errors.append(f"Row {i}: product_name exceeds 255 characters")
            continue
        rows.append({"vendor_name": vendor_name, "product_name": product_name})
    return rows, errors


async def _check_org_access(
    current_user: User, org_id: int, session: AsyncSession
) -> None:
    """Raise 403/404 if user can't access the org or the org doesn't exist."""
    if current_user.role != "admin" and current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = await session.execute(
        select(Organization).where(Organization.id == org_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Organization not found")


# ---- KEV autocomplete (not org-scoped) ----

@router.get("/vendors/autocomplete")
@limiter.limit(settings.RATE_LIMIT_DATA)
async def autocomplete_vendors(
    request: Request,  # noqa: ARG001
    q: Annotated[str, Query(min_length=1, max_length=255)],
    field: Annotated[str, Query(pattern=r"^(vendor|product)$")] = "vendor",
    vendor: Annotated[str | None, Query(max_length=255)] = None,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    session: AsyncSession = Depends(get_session),
):
    """Autocomplete vendor or product names from the KEV catalog."""
    if field == "vendor":
        col = KEV.vendor
    else:
        col = KEV.product

    stmt = select(col).distinct().where(col.ilike(f"{q}%")).order_by(col).limit(20)

    if field == "product" and vendor:
        stmt = stmt.where(KEV.vendor == vendor)

    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


# ---- Org-scoped vendor CRUD ----

@router.get("/organizations/{org_id}/vendors", response_model=OrgVendorListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_vendors(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgVendorRepository = Depends(get_vendor_repo),
    session: AsyncSession = Depends(get_session),
):
    """List vendors for an organization (paginated)."""
    await _check_org_access(current_user, org_id, session)
    try:
        items, total = await repo.list_vendors(org_id, page, page_size)
    except SQLAlchemyError:
        logger.exception("Failed to list vendors for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to list vendors")
    return OrgVendorListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[OrgVendorRead.model_validate(v) for v in items],
    )


@router.post("/organizations/{org_id}/vendors", response_model=OrgVendorRead, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def create_vendor(
    request: Request,  # noqa: ARG001
    org_id: int,
    body: OrgVendorCreate,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgVendorRepository = Depends(get_vendor_repo),
    session: AsyncSession = Depends(get_session),
):
    """Add a vendor to the organization's technology stack."""
    await _check_org_access(current_user, org_id, session)
    try:
        vendor = await repo.create(org_id, body)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Vendor/product combination already exists")
    except SQLAlchemyError:
        logger.exception("Failed to create vendor for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to add vendor")
    return vendor


@router.put("/organizations/{org_id}/vendors/{vendor_id}", response_model=OrgVendorRead)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def update_vendor(
    request: Request,  # noqa: ARG001
    org_id: int,
    vendor_id: int,
    body: OrgVendorUpdate,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgVendorRepository = Depends(get_vendor_repo),
    session: AsyncSession = Depends(get_session),
):
    """Update a vendor entry."""
    await _check_org_access(current_user, org_id, session)
    try:
        vendor = await repo.update(vendor_id, org_id, body)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Vendor/product combination already exists")
    except SQLAlchemyError:
        logger.exception("Failed to update vendor %s", vendor_id)
        raise HTTPException(status_code=500, detail="Failed to update vendor")
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.delete("/organizations/{org_id}/vendors/{vendor_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def delete_vendor(
    request: Request,  # noqa: ARG001
    org_id: int,
    vendor_id: int,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgVendorRepository = Depends(get_vendor_repo),
    session: AsyncSession = Depends(get_session),
):
    """Remove a vendor from the organization's technology stack."""
    await _check_org_access(current_user, org_id, session)
    try:
        deleted = await repo.delete(vendor_id, org_id)
    except SQLAlchemyError:
        logger.exception("Failed to delete vendor %s", vendor_id)
        raise HTTPException(status_code=500, detail="Failed to delete vendor")
    if not deleted:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return None


@router.post(
    "/organizations/{org_id}/vendors/import",
    response_model=OrgVendorImportResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def import_vendors_csv(
    request: Request,  # noqa: ARG001
    org_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    repo: SqlOrgVendorRepository = Depends(get_vendor_repo),
    session: AsyncSession = Depends(get_session),
):
    """Import vendors from a CSV file (max 500 rows).

    Expected CSV columns: vendor_name (required), product_name (optional).
    """
    await _check_org_access(current_user, org_id, session)

    if file.content_type and file.content_type not in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "vendor_name" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain a 'vendor_name' column",
        )

    rows, errors = _parse_csv_rows(reader)

    if not rows:
        return OrgVendorImportResponse(imported=0, skipped=0, errors=errors)

    try:
        imported, skipped = await repo.bulk_import(org_id, rows)
    except SQLAlchemyError:
        logger.exception("Failed to import vendors for org %s", org_id)
        raise HTTPException(status_code=500, detail="Failed to import vendors")

    return OrgVendorImportResponse(imported=imported, skipped=skipped, errors=errors)
