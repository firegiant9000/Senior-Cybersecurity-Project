"""Inventory upload + scan-run routes (Month 2 Phase C).

CSV inventory wedge: drag-drop a CSV, validate it, import it,
get a scan_run back. The same scan_run model is reused by the
M365 spike (Phase E) and the future agent path.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access
from app.core.limiter import limiter
from app.db.audit_log import AuditLog
from app.db.engine import get_session
from app.db.user import User
from app.repositories.assets import SqlAssetRepository, get_asset_repo
from app.repositories.asset_software import (
    SqlAssetSoftwareRepository,
    get_asset_software_repo,
)
from app.repositories.scan_runs import SqlScanRunRepository, get_scan_run_repo
from app.schemas.asset import AssetRead, AssetTagsUpdate
from app.schemas.asset_software import AssetSoftwareRead
from app.schemas.scan_run import (
    ScanRunCreate,
    ScanRunListResponse,
    ScanRunRead,
    ScanRunUpdate,
)
from app.services.inventory_import import (
    MAX_CSV_ROWS,
    commit_inventory,
    count_kev_matches,
    parse_csv,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Response models ----------------------------------------------------


class CsvRowError(BaseModel):
    row_number: int
    errors: list[str]


class CsvPreviewResponse(BaseModel):
    valid_rows: int
    invalid_rows: list[CsvRowError]
    distinct_assets: int
    distinct_software: int
    would_create: int
    would_update: int


class AssetWithKevResponse(BaseModel):
    """Asset list row with the literal-match KEV count."""

    asset: AssetRead
    kev_match_count: int = 0


class AssetWithKevListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AssetWithKevResponse]


class AssetDetailResponse(BaseModel):
    asset: AssetRead
    software: list[AssetSoftwareRead]


class AssetFindingMatch(BaseModel):
    """One KEV/CVE match against an asset's software (Phase F2).

    The pairing is a literal vendor+product match. Month 3's CPE matcher
    will replace this with version-aware lookups.
    """

    software_id: int
    vendor: str
    product: str
    version: str | None = None
    cve_id: str
    cvss_score: float | None = None
    severity: str | None = None
    in_kev: bool = False
    description: str | None = None


class AssetFindingsResponse(BaseModel):
    asset_id: int
    total: int
    items: list[AssetFindingMatch]
    note: str = (
        "Preliminary literal vendor+product match. Month 3's CPE matcher "
        "will replace this with version-aware lookups."
    )


class VendorAssetCount(BaseModel):
    vendor: str
    asset_count: int


class InventoryHealth(BaseModel):
    assets_total: int
    assets_with_known_software: int
    assets_with_kev_match: int
    last_inventory_update: str | None = None
    last_source: str | None = None
    top_vendors: list[VendorAssetCount] = []
    source: str = "assets_inventory"


# ---- Helpers ------------------------------------------------------------


async def _read_csv(file: UploadFile) -> str:
    if file.content_type and file.content_type not in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    raw = await file.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded") from None


async def _audit(
    session: AsyncSession,
    *,
    actor: User,
    org_id: int,
    action: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor.id,
            org_id=org_id,
            action=action,
            payload=payload,
        )
    )
    await session.flush()


# ---- CSV preview / import ----------------------------------------------


@router.post(
    "/organizations/{org_id}/inventory/uploads/csv/preview",
    response_model=CsvPreviewResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def preview_inventory_csv(
    request: Request,  # noqa: ARG001 — required by limiter
    org_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
):
    """Validate a CSV without writing anything.

    Returns counts the UI uses to render the "what would happen?" summary.
    No DB writes; safe to call repeatedly.
    """
    await check_org_access(current_user, org_id, session)
    text = await _read_csv(file)
    result = parse_csv(text)

    # Compute would_create vs would_update by hitting the assets table for
    # the distinct hostnames we parsed.
    would_update = 0
    if result.rows:
        hostnames = {r.hostname for r in result.rows}
        for hostname in hostnames:
            existing = await asset_repo.get_by_hostname(org_id, hostname)
            if existing is not None:
                would_update += 1

    return CsvPreviewResponse(
        valid_rows=result.valid_rows,
        invalid_rows=[CsvRowError(**e) for e in result.errors],
        distinct_assets=result.distinct_assets,
        distinct_software=result.distinct_software,
        would_create=max(0, result.distinct_assets - would_update),
        would_update=would_update,
    )


@router.post(
    "/organizations/{org_id}/inventory/uploads/csv/import",
    response_model=ScanRunRead,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def import_inventory_csv(
    request: Request,  # noqa: ARG001
    org_id: int,
    file: UploadFile,
    confirm: Annotated[bool, Query()] = False,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    """Commit a CSV import. Idempotent by (org_id, hostname).

    Creates a single ``scan_runs`` row, parses the CSV, upserts assets +
    asset_software, and runs a literal-match KEV scan over the
    inventory. Returns the populated scan_run; the frontend can poll
    ``GET /scan-runs/{id}`` for progress.
    """
    await check_org_access(current_user, org_id, session)
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true query parameter required to import",
        )

    text = await _read_csv(file)
    parsed = parse_csv(text)
    if not parsed.rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid rows to import. "
                f"{len(parsed.errors)} errors; first: "
                f"{parsed.errors[0]['errors'][0] if parsed.errors else 'unknown'}"
            ),
        )
    if len(parsed.rows) > MAX_CSV_ROWS:
        # Defensive: parse_csv enforces this, but the caller's intent matters.
        raise HTTPException(
            status_code=400, detail=f"CSV exceeds {MAX_CSV_ROWS}-row limit"
        )

    scan_run = await scan_repo.create(
        org_id,
        ScanRunCreate(
            source="csv_upload",
            triggered_by_user_id=current_user.id,
            metadata={
                "original_filename": file.filename,
                "submitted_rows": len(parsed.rows),
                "submitted_errors": len(parsed.errors),
            },
        ),
    )

    try:
        await scan_repo.update(
            scan_run.id, org_id, ScanRunUpdate(status="running")
        )
        asset_count, software_count = await commit_inventory(
            session, org_id=org_id, rows=parsed.rows, scan_run_id=scan_run.id
        )
        kev_matches = await count_kev_matches(session, org_id)
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("inventory import failed for org %s", org_id)
        await scan_repo.update(
            scan_run.id,
            org_id,
            ScanRunUpdate(
                status="failed",
                error_message=str(exc)[:1900],
                finished_at=datetime.now(timezone.utc),
            ),
        )
        raise HTTPException(status_code=500, detail="Failed to import inventory") from exc

    final = await scan_repo.update(
        scan_run.id,
        org_id,
        ScanRunUpdate(
            status="succeeded",
            asset_count=asset_count,
            software_count=software_count,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "original_filename": file.filename,
                "submitted_rows": len(parsed.rows),
                "submitted_errors": len(parsed.errors),
                "kev_matches": kev_matches,
            },
        ),
    )
    # Audit trail — separate transaction is fine; the import already
    # committed and an audit failure should not roll the data back.
    try:
        await _audit(
            session,
            actor=current_user,
            org_id=org_id,
            action="inventory.csv_import",
            payload={
                "scan_run_id": scan_run.id,
                "asset_count": asset_count,
                "software_count": software_count,
                "kev_matches": kev_matches,
                "original_filename": file.filename,
            },
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for scan_run %s", scan_run.id)

    return final or scan_run


# ---- Scan runs ----------------------------------------------------------


@router.get(
    "/organizations/{org_id}/scan-runs",
    response_model=ScanRunListResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_scan_runs(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    await check_org_access(current_user, org_id, session)
    items, total = await scan_repo.list_for_org(org_id, page, page_size)
    return ScanRunListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get(
    "/organizations/{org_id}/scan-runs/{scan_run_id}",
    response_model=ScanRunRead,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_scan_run(
    request: Request,  # noqa: ARG001
    org_id: int,
    scan_run_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    await check_org_access(current_user, org_id, session)
    run = await scan_repo.get_by_id(scan_run_id, org_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scan run not found")
    return run


# ---- Assets -------------------------------------------------------------


@router.get(
    "/organizations/{org_id}/assets",
    response_model=AssetWithKevListResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_assets(
    request: Request,  # noqa: ARG001
    org_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: Annotated[bool | None, Query()] = None,
    vendor: Annotated[str | None, Query(max_length=255)] = None,
    hostname: Annotated[str | None, Query(max_length=255)] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
):
    """List org assets with literal KEV-match counts.

    The KEV match count is computed on the fly via the existing CISA
    catalog (`vendor + product`, case-insensitive). Month 3 replaces this
    with the CPE matcher.
    """
    await check_org_access(current_user, org_id, session)
    items, total = await asset_repo.list_assets(
        org_id,
        page,
        page_size,
        is_active=is_active,
        hostname_search=hostname,
    )
    if not items:
        return AssetWithKevListResponse(
            total=total, page=page, page_size=page_size, items=[]
        )

    # Build (lower(vendor), lower(product)) → count for the visible assets
    # by joining asset_software ↔ kev_catalog.
    from sqlalchemy import func, select

    from app.db.asset_software import AssetSoftware
    from app.db.models import KEV

    asset_ids = [a.id for a in items]
    kev_pairs = (
        await session.execute(
            select(func.lower(KEV.vendor), func.lower(KEV.product)).distinct()
        )
    ).all()
    kev_set = {(row[0], row[1]) for row in kev_pairs}

    sw_rows = await session.execute(
        select(
            AssetSoftware.asset_id,
            func.lower(AssetSoftware.vendor),
            func.lower(AssetSoftware.product),
            func.count(AssetSoftware.id),
        )
        .where(
            AssetSoftware.org_id == org_id,
            AssetSoftware.asset_id.in_(asset_ids),
        )
        .group_by(
            AssetSoftware.asset_id,
            func.lower(AssetSoftware.vendor),
            func.lower(AssetSoftware.product),
        )
    )
    kev_counts: dict[int, int] = {}
    for asset_id, v, p, c in sw_rows.all():
        if (v, p) in kev_set:
            kev_counts[asset_id] = kev_counts.get(asset_id, 0) + int(c)

    # Filter by vendor if requested (server-side, after the KEV computation).
    out: list[AssetWithKevResponse] = []
    vendor_lower = vendor.lower() if vendor else None
    if vendor_lower:
        vendor_rows = await session.execute(
            select(AssetSoftware.asset_id)
            .where(
                AssetSoftware.org_id == org_id,
                func.lower(AssetSoftware.vendor) == vendor_lower,
                AssetSoftware.asset_id.in_(asset_ids),
            )
            .distinct()
        )
        keep_ids = {row[0] for row in vendor_rows.all()}
    else:
        keep_ids = set(asset_ids)

    for asset in items:
        if asset.id not in keep_ids:
            continue
        out.append(
            AssetWithKevResponse(
                asset=AssetRead.model_validate(asset, from_attributes=True),
                kev_match_count=kev_counts.get(asset.id, 0),
            )
        )
    return AssetWithKevListResponse(
        total=total if not vendor_lower else len(out),
        page=page,
        page_size=page_size,
        items=out,
    )


@router.get(
    "/organizations/{org_id}/assets/{asset_id}",
    response_model=AssetDetailResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_asset_detail(
    request: Request,  # noqa: ARG001
    org_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
    software_repo: SqlAssetSoftwareRepository = Depends(get_asset_software_repo),
):
    await check_org_access(current_user, org_id, session)
    asset = await asset_repo.get_by_id(asset_id, org_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    software = await software_repo.list_for_asset(asset_id, org_id)
    return AssetDetailResponse(
        asset=AssetRead.model_validate(asset, from_attributes=True),
        software=[
            AssetSoftwareRead.model_validate(s, from_attributes=True) for s in software
        ],
    )


@router.get(
    "/organizations/{org_id}/assets/{asset_id}/findings",
    response_model=AssetFindingsResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_asset_findings(
    request: Request,  # noqa: ARG001
    org_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
):
    """Return CVE/KEV matches for one asset (Phase F2).

    Literal (vendor, product) match between ``asset_software`` and the KEV
    catalog / NVD CVE table. KEV-listed CVEs come first; same-vendor NVD
    rows follow. The Month 3 CPE matcher will replace this.
    """
    from sqlalchemy import func, select

    from app.db.asset_software import AssetSoftware
    from app.db.models import CVE, KEV

    await check_org_access(current_user, org_id, session)
    asset = await asset_repo.get_by_id(asset_id, org_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    software_rows = (
        await session.execute(
            select(AssetSoftware).where(
                AssetSoftware.asset_id == asset_id,
                AssetSoftware.org_id == org_id,
            )
        )
    ).scalars().all()
    if not software_rows:
        return AssetFindingsResponse(asset_id=asset_id, total=0, items=[])

    pairs = {(s.vendor.lower(), s.product.lower()): s for s in software_rows}
    if not pairs:
        return AssetFindingsResponse(asset_id=asset_id, total=0, items=[])

    # KEV matches first (these have a CVE link).
    kev_q = (
        select(
            KEV.cve_id,
            KEV.vendor,
            KEV.product,
            CVE.cvss_score,
            CVE.severity,
            CVE.description,
        )
        .join(CVE, CVE.cve_id == KEV.cve_id)
        .where(
            func.lower(KEV.vendor).in_([v for v, _ in pairs]),
            func.lower(KEV.product).in_([p for _, p in pairs]),
        )
        .limit(500)
    )
    kev_rows = (await session.execute(kev_q)).all()

    items: list[AssetFindingMatch] = []
    seen_cves: set[str] = set()
    for cve_id, vendor, product, cvss, severity, description in kev_rows:
        key = (vendor.lower(), product.lower())
        if key not in pairs:
            continue
        sw = pairs[key]
        items.append(
            AssetFindingMatch(
                software_id=sw.id,
                vendor=sw.vendor,
                product=sw.product,
                version=sw.version,
                cve_id=cve_id,
                cvss_score=cvss,
                severity=severity,
                in_kev=True,
                description=description,
            )
        )
        seen_cves.add(cve_id)

    # NVD-second: surface NVD CVEs whose description literally mentions the
    # product name and aren't already covered by KEV. Marked ``in_kev=False``
    # so the UI can render them in a distinct section.
    await _append_nvd_matches(session, pairs, seen_cves, items)

    return AssetFindingsResponse(asset_id=asset_id, total=len(items), items=items)


# NVD CVEs aren't keyed by vendor/product; we only get a literal product-name
# match via description ILIKE. Cap per product to keep noise low — the Month 3
# CPE matcher replaces this entirely.
_NVD_PER_PRODUCT_CAP = 5


async def _append_nvd_matches(
    session: AsyncSession,
    pairs: dict[tuple[str, str], Any],
    seen_cves: set[str],
    items: list[AssetFindingMatch],
) -> None:
    from sqlalchemy import func, select

    from app.db.models import CVE

    for (_vendor, product), sw in pairs.items():
        if not product or len(product) < 3:
            # Skip 1-2 char "products" — they explode the LIKE result set.
            continue
        like = f"%{product.lower()}%"
        nvd_q = (
            select(CVE.cve_id, CVE.cvss_score, CVE.severity, CVE.description)
            .where(func.lower(CVE.description).like(like))
            .order_by(CVE.cvss_score.desc().nullslast())
            .limit(_NVD_PER_PRODUCT_CAP * 4)  # over-fetch; we filter seen_cves below
        )
        added = 0
        for cve_id, cvss, severity, description in (
            await session.execute(nvd_q)
        ).all():
            if cve_id in seen_cves:
                continue
            items.append(
                AssetFindingMatch(
                    software_id=sw.id,
                    vendor=sw.vendor,
                    product=sw.product,
                    version=sw.version,
                    cve_id=cve_id,
                    cvss_score=cvss,
                    severity=severity,
                    in_kev=False,
                    description=description,
                )
            )
            seen_cves.add(cve_id)
            added += 1
            if added >= _NVD_PER_PRODUCT_CAP:
                break


@router.get(
    "/organizations/{org_id}/inventory/health",
    response_model=InventoryHealth,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_inventory_health(
    request: Request,  # noqa: ARG001
    org_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Inventory summary used by the overview tab's InventoryHealthCard (Phase F3)."""
    from sqlalchemy import func, select

    from app.db.asset import Asset
    from app.db.asset_software import AssetSoftware
    from app.db.models import KEV
    from app.db.scan_run import ScanRun

    await check_org_access(current_user, org_id, session)

    assets_total = int(
        (
            await session.execute(
                select(func.count(Asset.id)).where(Asset.org_id == org_id)
            )
        ).scalar_one()
    )

    assets_with_software = int(
        (
            await session.execute(
                select(func.count(func.distinct(AssetSoftware.asset_id))).where(
                    AssetSoftware.org_id == org_id
                )
            )
        ).scalar_one()
    )

    # Asset-count with at least one literal KEV (vendor, product) match.
    kev_match_assets = (
        await session.execute(
            select(func.count(func.distinct(AssetSoftware.asset_id)))
            .select_from(AssetSoftware)
            .join(
                KEV,
                (func.lower(AssetSoftware.vendor) == func.lower(KEV.vendor))
                & (func.lower(AssetSoftware.product) == func.lower(KEV.product)),
            )
            .where(AssetSoftware.org_id == org_id)
        )
    ).scalar_one()
    assets_with_kev = int(kev_match_assets or 0)

    last_run = (
        await session.execute(
            select(ScanRun.started_at, ScanRun.source)
            .where(ScanRun.org_id == org_id)
            .order_by(ScanRun.started_at.desc())
            .limit(1)
        )
    ).first()
    last_inventory_update = (
        last_run[0].isoformat() if last_run and last_run[0] is not None else None
    )
    last_source = last_run[1] if last_run else None

    # Top vendors by distinct asset count — drives the chips on the Assets tab.
    top_vendor_rows = (
        await session.execute(
            select(
                AssetSoftware.vendor,
                func.count(func.distinct(AssetSoftware.asset_id)).label("asset_count"),
            )
            .where(AssetSoftware.org_id == org_id)
            .group_by(AssetSoftware.vendor)
            .order_by(func.count(func.distinct(AssetSoftware.asset_id)).desc())
            .limit(5)
        )
    ).all()
    top_vendors = [
        VendorAssetCount(vendor=v, asset_count=int(c)) for v, c in top_vendor_rows
    ]

    return InventoryHealth(
        assets_total=assets_total,
        assets_with_known_software=assets_with_software,
        assets_with_kev_match=assets_with_kev,
        last_inventory_update=last_inventory_update,
        last_source=last_source,
        top_vendors=top_vendors,
    )


# ---- N5: Asset tagging --------------------------------------------------


@router.put(
    "/organizations/{org_id}/assets/{asset_id}/tags",
    response_model=AssetRead,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def set_asset_tags(
    request: Request,  # noqa: ARG001
    org_id: int,
    asset_id: int,
    body: AssetTagsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
):
    """Replace the tag list on an asset.

    Tags are free-text labels (e.g. ``production``, ``pci-zone``,
    ``executive-laptop``) that drive prioritization filters. Tags are
    normalized to lowercase, whitespace-collapsed, deduplicated, and
    capped at 64 chars each.
    """
    await check_org_access(current_user, org_id, session)
    updated = await asset_repo.set_tags(asset_id, org_id, body.tags)
    if updated is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        await _audit(
            session,
            actor=current_user,
            org_id=org_id,
            action="asset.tags_updated",
            payload={"asset_id": asset_id, "tags": updated.tags or []},
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for asset.tags_updated %s", asset_id)
    return AssetRead.model_validate(updated, from_attributes=True)


# ---- N3: Inventory diff between scan_runs -------------------------------


class ScanRunDiff(BaseModel):
    scan_run_id: int
    previous_scan_run_id: int | None
    assets_added: int
    assets_refreshed: int
    software_added: int
    note: str = (
        "Compares this scan_run against the previous successful run of the "
        "same source. 'Added' = rows whose created_by_scan_run_id matches "
        "this run."
    )


@router.get(
    "/organizations/{org_id}/scan-runs/{scan_run_id}/diff",
    response_model=ScanRunDiff,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_scan_run_diff(
    request: Request,  # noqa: ARG001
    org_id: int,
    scan_run_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    """How many assets/software did this scan_run actually change?

    "Added" is counted from the provenance FK landed in migration 044.
    "Refreshed" subtracts that from the scan_run's reported asset_count to
    estimate the merge-into-existing slice.
    """
    from sqlalchemy import func, select

    from app.db.asset import Asset
    from app.db.asset_software import AssetSoftware
    from app.db.scan_run import ScanRun

    await check_org_access(current_user, org_id, session)
    run = await scan_repo.get_by_id(scan_run_id, org_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scan run not found")

    assets_added = int(
        (
            await session.execute(
                select(func.count(Asset.id)).where(
                    Asset.org_id == org_id,
                    Asset.created_by_scan_run_id == scan_run_id,
                )
            )
        ).scalar_one()
    )
    software_added = int(
        (
            await session.execute(
                select(func.count(AssetSoftware.id)).where(
                    AssetSoftware.org_id == org_id,
                    AssetSoftware.created_by_scan_run_id == scan_run_id,
                )
            )
        ).scalar_one()
    )
    assets_refreshed = max(0, (run.asset_count or 0) - assets_added)

    previous = (
        await session.execute(
            select(ScanRun.id)
            .where(
                ScanRun.org_id == org_id,
                ScanRun.source == run.source,
                ScanRun.status == "succeeded",
                ScanRun.id != scan_run_id,
                ScanRun.started_at < run.started_at,
            )
            .order_by(ScanRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return ScanRunDiff(
        scan_run_id=scan_run_id,
        previous_scan_run_id=previous,
        assets_added=assets_added,
        assets_refreshed=assets_refreshed,
        software_added=software_added,
    )


# ---- N9: Rollback a scan_run --------------------------------------------


class ScanRunRollbackResponse(BaseModel):
    scan_run_id: int
    assets_deleted: int
    software_deleted: int
    note: str = (
        "Rollback deletes rows this scan_run created (tracked via "
        "created_by_scan_run_id). Refresh-only updates to pre-existing rows "
        "are NOT reverted — full point-in-time snapshots are out of scope."
    )


@router.post(
    "/organizations/{org_id}/scan-runs/{scan_run_id}/rollback",
    response_model=ScanRunRollbackResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def rollback_scan_run(
    request: Request,  # noqa: ARG001
    org_id: int,
    scan_run_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    """Undo an inventory upload.

    Deletes assets + asset_software whose ``created_by_scan_run_id`` matches
    the given run, then marks the scan_run ``status='rolled_back'``.
    """
    from sqlalchemy import delete

    from app.db.asset import Asset
    from app.db.asset_software import AssetSoftware

    await check_org_access(current_user, org_id, session)
    run = await scan_repo.get_by_id(scan_run_id, org_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scan run not found")
    if run.status == "rolled_back":
        raise HTTPException(status_code=409, detail="Scan run already rolled back")

    sw_deleted = (
        await session.execute(
            delete(AssetSoftware).where(
                AssetSoftware.org_id == org_id,
                AssetSoftware.created_by_scan_run_id == scan_run_id,
            )
        )
    ).rowcount or 0
    assets_deleted = (
        await session.execute(
            delete(Asset).where(
                Asset.org_id == org_id,
                Asset.created_by_scan_run_id == scan_run_id,
            )
        )
    ).rowcount or 0

    # Stamp the scan_run with the rolled_back terminal state. We use the raw
    # column update because ``ScanRunUpdate`` constrains status to the
    # pipeline-progress values.
    run.status = "rolled_back"
    existing_meta = dict(run.scan_metadata or {})
    existing_meta["rolled_back_by_user_id"] = current_user.id
    existing_meta["rolled_back_assets"] = int(assets_deleted)
    existing_meta["rolled_back_software"] = int(sw_deleted)
    run.scan_metadata = existing_meta
    await session.commit()

    try:
        await _audit(
            session,
            actor=current_user,
            org_id=org_id,
            action="inventory.rollback",
            payload={
                "scan_run_id": scan_run_id,
                "assets_deleted": int(assets_deleted),
                "software_deleted": int(sw_deleted),
            },
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for inventory.rollback %s", scan_run_id)

    return ScanRunRollbackResponse(
        scan_run_id=scan_run_id,
        assets_deleted=int(assets_deleted),
        software_deleted=int(sw_deleted),
    )


# ---- N8: Asset risk summary --------------------------------------------


class AssetRiskRow(BaseModel):
    asset_id: int
    hostname: str
    max_cvss: float | None
    max_epss_percentile: float | None
    risk_score: float
    in_kev: bool


class AssetRiskSummary(BaseModel):
    org_id: int
    items: list[AssetRiskRow]
    note: str = (
        "Per-asset risk = max(software CVSS) + (max EPSS percentile / 10). "
        "Literal vendor+product match against KEV/NVD; refined by the Month "
        "3 CPE matcher."
    )
    source: str = "assets_inventory"


@router.get(
    "/organizations/{org_id}/inventory/risk-summary",
    response_model=AssetRiskSummary,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_asset_risk_summary(
    request: Request,  # noqa: ARG001
    org_id: int,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Rank assets by max-CVSS + EPSS-percentile/10.

    A simple risk surface to render the "riskiest asset" overview tile —
    once the Month 3 CPE matcher lands the underlying CVE matching gets
    accurate, but the score formula itself stays the same.
    """
    from sqlalchemy import func, select

    from app.db.asset import Asset
    from app.db.asset_software import AssetSoftware
    from app.db.models import CVE, KEV

    await check_org_access(current_user, org_id, session)

    # Pull every software row for the org and the matching CVE max-stats per
    # (vendor, product). We compute the risk in Python because we need to
    # group by asset_id (an attribute of asset_software, not of CVE) and the
    # KEV/CVE side has no asset_id.
    sw_rows = (
        await session.execute(
            select(
                AssetSoftware.asset_id,
                AssetSoftware.vendor,
                AssetSoftware.product,
            ).where(AssetSoftware.org_id == org_id)
        )
    ).all()
    if not sw_rows:
        return AssetRiskSummary(org_id=org_id, items=[])

    # (vendor_lower, product_lower) → (max_cvss, max_epss_percentile)
    pair_stats: dict[tuple[str, str], tuple[float | None, float | None]] = {}
    pairs = {(v.lower(), p.lower()) for _, v, p in sw_rows}
    if pairs:
        # Pull NVD stats by description-LIKE-product is too expensive here;
        # the literal join the rest of inventory.py uses is via KEV, which
        # has (vendor, product) columns. We use KEV ↔ CVE for the CVSS and
        # the CVE table directly for EPSS.
        kev_rows = (
            await session.execute(
                select(
                    func.lower(KEV.vendor),
                    func.lower(KEV.product),
                    func.max(CVE.cvss_score),
                    func.max(CVE.epss_percentile),
                )
                .join(CVE, CVE.cve_id == KEV.cve_id)
                .group_by(func.lower(KEV.vendor), func.lower(KEV.product))
            )
        ).all()
        for v, p, max_cvss, max_eps in kev_rows:
            if (v, p) in pairs:
                pair_stats[(v, p)] = (
                    float(max_cvss) if max_cvss is not None else None,
                    float(max_eps) if max_eps is not None else None,
                )

    # Aggregate per-asset.
    per_asset: dict[int, tuple[float | None, float | None, bool]] = {}
    for asset_id, vendor, product in sw_rows:
        key = (vendor.lower(), product.lower())
        cur = per_asset.get(asset_id, (None, None, False))
        max_cvss, max_eps, in_kev = cur
        stats = pair_stats.get(key)
        if stats is None:
            per_asset[asset_id] = (max_cvss, max_eps, in_kev)
            continue
        s_cvss, s_eps = stats
        new_cvss = max(filter(lambda x: x is not None, [max_cvss, s_cvss]), default=None)
        new_eps = max(filter(lambda x: x is not None, [max_eps, s_eps]), default=None)
        per_asset[asset_id] = (new_cvss, new_eps, True)

    # Resolve hostnames for the top-N to avoid loading every asset row.
    scored: list[tuple[int, float | None, float | None, bool, float]] = []
    for asset_id, (max_cvss, max_eps, in_kev) in per_asset.items():
        score = (max_cvss or 0.0) + ((max_eps or 0.0) / 10.0)
        scored.append((asset_id, max_cvss, max_eps, in_kev, score))
    scored.sort(key=lambda r: r[4], reverse=True)
    top = scored[:limit]
    if not top:
        return AssetRiskSummary(org_id=org_id, items=[])

    top_ids = [t[0] for t in top]
    hostnames = {
        row.id: row.hostname
        for row in (
            await session.execute(
                select(Asset).where(Asset.id.in_(top_ids), Asset.org_id == org_id)
            )
        ).scalars().all()
    }
    return AssetRiskSummary(
        org_id=org_id,
        items=[
            AssetRiskRow(
                asset_id=aid,
                hostname=hostnames.get(aid, "?"),
                max_cvss=mc,
                max_epss_percentile=me,
                risk_score=round(score, 3),
                in_kev=ink,
            )
            for aid, mc, me, ink, score in top
        ],
    )
