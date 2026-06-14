"""Inventory upload + scan-run routes (Month 2 Phase C).

CSV inventory wedge: drag-drop a CSV, validate it, import it,
get a scan_run back. The same scan_run model is reused by the
M365 spike (Phase E) and the future agent path.
"""

import logging
from datetime import UTC, datetime, timedelta
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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.v1.auth import get_current_user
from app.core.config import settings
from app.core.dependencies import check_org_access, get_agent_from_token
from app.core.limiter import agent_token_key, limiter
from app.db.agent_enrollment import AgentEnrollment
from app.db.audit_log import AuditLog
from app.db.engine import get_session
from app.db.user import User
from app.repositories.agent_scan_nonces import (
    SqlAgentScanNonceRepository,
    get_agent_scan_nonce_repo,
)
from app.repositories.asset_findings import (
    ALLOWED_FINDING_STATUSES,
    SqlAssetFindingRepository,
    get_asset_finding_repo,
)
from app.repositories.asset_software import (
    SqlAssetSoftwareRepository,
    get_asset_software_repo,
)
from app.repositories.assets import SqlAssetRepository, get_asset_repo
from app.repositories.scan_runs import SqlScanRunRepository, get_scan_run_repo
from app.schemas.agent_scan import AgentScanPayload, ScanUploadAccepted
from app.schemas.asset import AssetRead, AssetTagsUpdate
from app.schemas.asset_software import AssetSoftwareRead
from app.schemas.scan_run import (
    ScanRunCreate,
    ScanRunListResponse,
    ScanRunRead,
    ScanRunUpdate,
)
from app.services import agent_scan
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
    # Latest agent-reported host observations (empty for CSV/M365-only assets).
    services: list[dict[str, Any]] = []
    listening_ports: list[dict[str, Any]] = []


class AssetFindingMatch(BaseModel):
    """One persisted version-aware CVE match against an asset's software.

    Produced by the Month 3 CPE matcher (Phase 2) and stored in
    ``asset_findings`` (Phase 3). Carries the confidence tier, per-finding
    risk score/tier, and remediation status.
    """

    finding_id: int
    software_id: int
    vendor: str
    product: str
    version: str | None = None
    cve_id: str
    cvss_score: float | None = None
    epss_score: float | None = None
    severity: str | None = None
    in_kev: bool = False
    match_confidence: str
    risk_score: float | None = None
    risk_tier: str
    status: str = "open"
    remediation_summary: str | None = None
    description: str | None = None


class AssetFindingsResponse(BaseModel):
    asset_id: int
    total: int
    items: list[AssetFindingMatch]
    note: str = (
        "Version-aware CPE matcher results, persisted in asset_findings. "
        "Confidence tiers: high/medium/low/needs_review."
    )


class FindingStatusUpdate(BaseModel):
    status: str
    remediation_summary: str | None = None


class FindingStatusResponse(BaseModel):
    finding_id: int
    status: str


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
    confirm: Annotated[bool, Query()] = False,  # noqa: FBT002 — FastAPI query param
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
        raise HTTPException(status_code=400, detail=f"CSV exceeds {MAX_CSV_ROWS}-row limit")

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
        await scan_repo.update(scan_run.id, org_id, ScanRunUpdate(status="running"))
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
                finished_at=datetime.now(UTC),
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
            finished_at=datetime.now(UTC),
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

    # Month 3 Phase 4: kick off version-aware matching off the request path so
    # the new inventory auto-populates asset_findings without a manual refresh.
    # run_matcher_for_org opens its own session, so it outlives this request;
    # trigger_matcher_async keeps a strong ref so the task isn't GC'd mid-run.
    from app.workers.matcher_job import trigger_matcher_async

    trigger_matcher_async(org_id, trigger="csv_import")

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


# ---- Agent scan upload (Month 4 Phase 3) --------------------------------
#
# These two routes authenticate by the agent bearer token (get_agent_from_token),
# NOT Firebase. The org is derived from the resolved enrollment — the agent can
# never assert an arbitrary org. The payload contract is frozen in
# schemas/agent_scan.py; the ingest path reuses commit_inventory + the matcher
# exactly like the CSV wedge.


async def _audit_agent(
    session: AsyncSession,
    *,
    org_id: int,
    action: str,
    payload: dict[str, Any],
) -> None:
    """Audit an agent action. Unlike ``_audit`` there is no human actor, so
    ``actor_user_id`` is null and the enrolled agent id lives in the payload."""
    session.add(AuditLog(actor_user_id=None, org_id=org_id, action=action, payload=payload))
    await session.flush()


@router.post("/inventory/scans", response_model=ScanUploadAccepted, status_code=201)
@limiter.limit(settings.RATE_LIMIT_AGENT_UPLOAD, key_func=agent_token_key)
async def upload_agent_scan(
    request: Request,  # noqa: ARG001 — required by limiter
    payload: AgentScanPayload,
    enrollment: AgentEnrollment = Depends(get_agent_from_token),
    session: AsyncSession = Depends(get_session),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
    nonce_repo: SqlAgentScanNonceRepository = Depends(get_agent_scan_nonce_repo),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
):
    """Ingest a read-only host scan from an enrolled agent.

    Auth is the agent bearer token; the org is the token's org. Validates the
    versioned schema, rejects replays and below-min scanners, persists a
    ``scan_run`` (source=agent), upserts assets/software via ``commit_inventory``,
    and kicks off the CPE matcher. The agent polls ``GET /inventory/scans/{id}``.
    """
    org_id = enrollment.org_id

    # Version gates first — cheap, and an old/unknown scanner should fail loudly
    # before we touch the DB.
    try:
        agent_scan.assert_schema_supported(payload.schema_version)
        agent_scan.assert_scanner_version_allowed(
            payload.scanner_version, settings.MIN_AGENT_VERSION
        )
    except agent_scan.ScanRejectedError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # Replay fast-path: reject a duplicate (scan_id, nonce) inside the window
    # before creating an orphan scan_run. The unique constraint below is the
    # backstop for a concurrent double-POST that races past this check.
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=settings.AGENT_SCAN_REPLAY_WINDOW_HOURS)
    if await nonce_repo.seen_within(payload.scan_id, payload.nonce, window_start):
        raise HTTPException(status_code=409, detail="Duplicate scan submission (replay detected)")

    rows = agent_scan.payload_to_rows(payload)
    base_meta = {
        "hostname": payload.host.hostname,
        "scanner_version": payload.scanner_version,
        "schema_version": payload.schema_version,
        "scan_id": payload.scan_id,
        "raw_payload_hash": agent_scan.payload_hash(payload),
        "submitted_software": len(payload.software),
        "agent_enrollment_id": enrollment.id,
    }
    scan_run = await scan_repo.create(
        org_id,
        ScanRunCreate(source="agent", triggered_by_user_id=None, metadata=base_meta),
    )

    try:
        await scan_repo.update(scan_run.id, org_id, ScanRunUpdate(status="running"))
        # Record the replay marker in the same transaction as the import so a
        # failed import frees the (scan_id, nonce) for a legit retry.
        await nonce_repo.record(
            org_id=org_id,
            agent_enrollment_id=enrollment.id,
            scan_id=payload.scan_id,
            nonce=payload.nonce,
        )
        asset_count, software_count = await commit_inventory(
            session, org_id=org_id, rows=rows, scan_run_id=scan_run.id, source="agent"
        )
        # Persist the host's services/ports snapshot onto its asset. The agent
        # reports exactly one host per payload, so resolve that single asset and
        # overwrite only the fields this scan actually reported (None = skip).
        services, listening_ports = agent_scan.extract_observations(payload)
        if services is not None or listening_ports is not None:
            asset = await asset_repo.get_by_hostname(org_id, payload.host.hostname)
            if asset is not None:
                if services is not None:
                    asset.services = services
                if listening_ports is not None:
                    asset.listening_ports = listening_ports
        await session.commit()
    except IntegrityError as exc:
        # Lost the race to the unique (scan_id, nonce) constraint → replay.
        await session.rollback()
        await scan_repo.update(
            scan_run.id,
            org_id,
            ScanRunUpdate(
                status="failed",
                error_message="duplicate scan submission",
                finished_at=datetime.now(UTC),
            ),
        )
        raise HTTPException(
            status_code=409, detail="Duplicate scan submission (replay detected)"
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("agent scan import failed for org %s", org_id)
        await scan_repo.update(
            scan_run.id,
            org_id,
            ScanRunUpdate(
                status="failed", error_message=str(exc)[:1900], finished_at=datetime.now(UTC)
            ),
        )
        raise HTTPException(status_code=500, detail="Failed to import scan") from exc

    final = await scan_repo.update(
        scan_run.id,
        org_id,
        ScanRunUpdate(
            status="succeeded",
            asset_count=asset_count,
            software_count=software_count,
            finished_at=datetime.now(UTC),
            metadata={**base_meta, "asset_count": asset_count, "software_count": software_count},
        ),
    )

    try:
        await _audit_agent(
            session,
            org_id=org_id,
            action="inventory.agent_scan",
            payload={
                "scan_run_id": scan_run.id,
                "agent_enrollment_id": enrollment.id,
                "asset_count": asset_count,
                "software_count": software_count,
                "scanner_version": payload.scanner_version,
            },
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for agent scan_run %s", scan_run.id)

    # Reuse the Month 3 matcher off the request path, same as CSV import.
    from app.workers.matcher_job import trigger_matcher_async

    trigger_matcher_async(org_id, trigger="agent_scan")

    return ScanUploadAccepted(
        scan_run_id=scan_run.id,
        status=(final or scan_run).status,
        asset_count=asset_count,
        software_count=software_count,
    )


@router.get("/inventory/scans/{scan_run_id}", response_model=ScanRunRead)
@limiter.limit(settings.RATE_LIMIT_AGENT_UPLOAD, key_func=agent_token_key)
async def get_agent_scan_status(
    request: Request,  # noqa: ARG001
    scan_run_id: int,
    enrollment: AgentEnrollment = Depends(get_agent_from_token),
    scan_repo: SqlScanRunRepository = Depends(get_scan_run_repo),
):
    """Let an agent poll its own scan_run status (org scoped to the token)."""
    run = await scan_repo.get_by_id(scan_run_id, enrollment.org_id)
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
        return AssetWithKevListResponse(total=total, page=page, page_size=page_size, items=[])

    # Build (lower(vendor), lower(product)) → count for the visible assets
    # by joining asset_software ↔ kev_catalog.
    from sqlalchemy import func, select

    from app.db.asset_software import AssetSoftware
    from app.db.models import KEV

    asset_ids = [a.id for a in items]
    kev_pairs = (
        await session.execute(select(func.lower(KEV.vendor), func.lower(KEV.product)).distinct())
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
        software=[AssetSoftwareRead.model_validate(s, from_attributes=True) for s in software],
        services=asset.services or [],
        listening_ports=asset.listening_ports or [],
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
    refresh: Annotated[bool, Query()] = False,  # noqa: FBT002 — FastAPI query param
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    asset_repo: SqlAssetRepository = Depends(get_asset_repo),
    software_repo: SqlAssetSoftwareRepository = Depends(get_asset_software_repo),
    finding_repo: SqlAssetFindingRepository = Depends(get_asset_finding_repo),
):
    """Return persisted version-aware CVE findings for one asset (Month 3 Phase 3).

    Reads from ``asset_findings`` (produced by the Phase 2 CPE matcher). When the
    asset has no persisted findings yet — or ``refresh=true`` is passed — the
    matcher is run and the results materialized first. Findings are returned
    riskiest-first with their confidence tier and remediation status.
    """
    from sqlalchemy import select

    from app.db.models import CVE
    from app.services.asset_findings_service import AssetFindingsService
    from app.services.risk_scorer import tier_for

    await check_org_access(current_user, org_id, session)
    asset = await asset_repo.get_by_id(asset_id, org_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    if refresh or await finding_repo.count_for_asset(asset_id, org_id) == 0:
        await AssetFindingsService(session).compute_and_persist_for_asset(asset_id, org_id)

    findings = await finding_repo.list_for_asset(asset_id, org_id)
    if not findings:
        return AssetFindingsResponse(asset_id=asset_id, total=0, items=[])

    # Resolve software vendor/product/version and CVE descriptions in two
    # bulk lookups rather than per-row queries.
    software = {s.id: s for s in await software_repo.list_for_asset(asset_id, org_id)}
    cve_ids = {f.cve_id for f in findings}
    descriptions = {
        str(cid).upper(): desc
        for cid, desc in (
            await session.execute(
                select(CVE.cve_id, CVE.description).where(CVE.cve_id.in_(cve_ids))
            )
        ).all()
    }

    items: list[AssetFindingMatch] = []
    for f in findings:
        sw = software.get(f.asset_software_id)
        items.append(
            AssetFindingMatch(
                finding_id=f.id,
                software_id=f.asset_software_id,
                vendor=sw.vendor if sw else "",
                product=sw.product if sw else "",
                version=sw.version if sw else None,
                cve_id=f.cve_id,
                cvss_score=f.cvss_score,
                epss_score=f.epss_score,
                severity=f.severity,
                in_kev=f.kev_flag,
                match_confidence=f.match_confidence,
                risk_score=f.risk_score,
                risk_tier=tier_for(f.match_confidence, f.risk_score),
                status=f.status,
                remediation_summary=f.remediation_summary,
                description=descriptions.get(f.cve_id.upper()),
            )
        )

    return AssetFindingsResponse(asset_id=asset_id, total=len(items), items=items)


@router.patch(
    "/organizations/{org_id}/assets/{asset_id}/findings/{finding_id}/status",
    response_model=FindingStatusResponse,
)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def patch_asset_finding_status(
    request: Request,  # noqa: ARG001
    org_id: int,
    asset_id: int,
    finding_id: int,
    body: FindingStatusUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    finding_repo: SqlAssetFindingRepository = Depends(get_asset_finding_repo),
):
    """Move a finding through its remediation status workflow.

    Statuses: ``open | accepted_risk | false_positive | in_progress | fixed``.
    Reporting ``false_positive`` stamps the acting user onto
    ``false_positive_reported_by``; any other status clears it.
    """
    await check_org_access(current_user, org_id, session)
    if body.status not in ALLOWED_FINDING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_FINDING_STATUSES)}",
        )
    existing = await finding_repo.get(finding_id, org_id)
    if existing is None or existing.asset_id != asset_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    remediation = body.remediation_summary[:5000] if body.remediation_summary else None
    updated = await finding_repo.update_status(
        finding_id,
        org_id,
        body.status,
        reported_by=current_user.id,
        remediation_summary=remediation,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    try:
        await _audit(
            session,
            actor=current_user,
            org_id=org_id,
            action="asset_finding.status_updated",
            payload={
                "finding_id": finding_id,
                "asset_id": asset_id,
                "status": body.status,
            },
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception("audit log failed for asset_finding.status_updated %s", finding_id)

    return FindingStatusResponse(finding_id=finding_id, status=updated.status)


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
            await session.execute(select(func.count(Asset.id)).where(Asset.org_id == org_id))
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
    top_vendors = [VendorAssetCount(vendor=v, asset_count=int(c)) for v, c in top_vendor_rows]

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
        )
        .scalars()
        .all()
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
