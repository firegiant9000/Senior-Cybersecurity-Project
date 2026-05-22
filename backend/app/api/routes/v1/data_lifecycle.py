"""Data-lifecycle endpoints — org deletion + full export.

Both operations are admin-gated and write an ``audit_log`` row recording
the actor, action and target org. Deletion iterates the org-scoped tables
explicitly so that adding a new tenant-scoped table in the future surfaces
here rather than silently relying on FK cascades that may not exist.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import delete, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.db.ai_summary_feedback import AISummaryFeedback
from app.db.ai_summary_generation import AISummaryGeneration
from app.db.assessment_submission import AssessmentSubmission
from app.db.audit_log import AuditLog
from app.db.engine import AsyncSessionLocal, get_session
from app.db.finding_status import FindingStatus
from app.db.findings_snapshot import FindingsSnapshot
from app.db.invitation import Invitation
from app.db.membership import Membership
from app.db.normalization_log import NormalizationLog
from app.db.org_domain import OrgDomain
from app.db.org_invite import OrgInvite
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.db.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Tables that are scoped by ``org_id`` and must be cleared as part of org
# deletion. Listed explicitly so a future tenant-scoped table doesn't quietly
# slip past the cascade (FK cascade is not assumed — some tables intentionally
# use SET NULL, others have no FK at all).
_ORG_SCOPED_MODELS_BY_ORG_ID: tuple[type, ...] = (
    AISummaryFeedback,
    AISummaryGeneration,
    FindingStatus,
    FindingsSnapshot,
    Invitation,
    Membership,
    NormalizationLog,
    OrgDomain,
    OrgInvite,
    OrgUpload,
    OrgVendor,
)


async def _delete_org_scoped_rows(session: AsyncSession, org_id: int) -> dict[str, int]:
    """Delete rows for the org across all known tenant-scoped tables.

    Returns a per-table count for the audit log payload.
    """
    counts: dict[str, int] = {}
    for model in _ORG_SCOPED_MODELS_BY_ORG_ID:
        result = await session.execute(
            delete(model).where(model.org_id == org_id)  # type: ignore[attr-defined]
        )
        counts[model.__tablename__] = int(result.rowcount or 0)

    # assessment_submissions uses ``organization_id`` rather than ``org_id``.
    result = await session.execute(
        delete(AssessmentSubmission).where(AssessmentSubmission.organization_id == org_id)
    )
    counts[AssessmentSubmission.__tablename__] = int(result.rowcount or 0)

    # Detach users from the org before removing the row (FK is ON DELETE SET
    # NULL but doing it explicitly keeps the deletion observable here).
    result = await session.execute(
        update(User).where(User.org_id == org_id).values(org_id=None, org_role=None)
    )
    counts["users_detached"] = int(result.rowcount or 0)

    return counts


def _coerce(value: Any) -> Any:
    """Best-effort JSON-friendly coercion for SQLAlchemy row values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


async def _write_audit_log_and_flush(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    org_id: int,
    action: str,
    payload: dict[str, Any] | None,
) -> None:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        org_id=org_id,
        action=action,
        payload=payload,
    )
    session.add(entry)
    # Flush so the INSERT is materialized while the FK target (organizations.id)
    # still exists. The session uses autoflush=False, and the delete route
    # issues a CORE DELETE against organizations before commit; without an
    # explicit flush here, the pending INSERT would be reordered after the
    # parent delete at commit time.
    await session.flush()


@router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_organization(
    org_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role("admin")),
) -> Response:
    """Hard-delete an organisation and every row scoped to it.

    Writes a single ``audit_log`` entry summarising the per-table delete
    counts before the org row itself is removed. Cascade is performed in
    application code rather than via FK cascade so newly added tenant
    tables surface here.
    """
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        counts = await _delete_org_scoped_rows(session, org_id)
        await _write_audit_log_and_flush(
            session,
            actor_user_id=current_user.id,
            org_id=org_id,
            action="organization.delete",
            payload={
                "deleted_counts": counts,
                "org_name": org.name,
                # Preserved so the audit trail survives the FK ON DELETE SET
                # NULL on audit_log.org_id once the org row is removed below.
                "original_org_id": org_id,
            },
        )
        await session.execute(delete(Organization).where(Organization.id == org_id))
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("Failed to delete organization %s: %s", org_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete organization") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/organizations/{org_id}/export")
async def export_organization(
    org_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role("admin")),
) -> StreamingResponse:
    """Stream a JSON bundle of every row tied to the organisation.

    Result is not persisted server-side — caller is expected to capture the
    response body. An ``audit_log`` row is written before the stream begins
    so failed downloads still leave a trace.

    The body is emitted incrementally so an org with a large
    ``ai_summary_generations`` or ``findings_snapshots`` history doesn't
    materialise the entire JSON document in memory.
    """
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    org_payload = {
        col.name: _coerce(getattr(org, col.name)) for col in Organization.__table__.columns
    }

    table_specs: list[tuple[str, str]] = [
        (model.__tablename__, "org_id") for model in _ORG_SCOPED_MODELS_BY_ORG_ID
    ]
    table_specs.append((AssessmentSubmission.__tablename__, "organization_id"))

    row_counts: dict[str, int] = {}
    for table_name, fk_column in table_specs:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM {table_name} WHERE {fk_column} = :org_id"),
            {"org_id": org_id},
        )
        row_counts[table_name] = int(count_result.scalar() or 0)

    await _write_audit_log_and_flush(
        session,
        actor_user_id=current_user.id,
        org_id=org_id,
        action="organization.export",
        payload={"row_counts": row_counts},
    )
    await session.commit()

    async def _stream_bundle():
        import json

        exported_at = datetime.utcnow().isoformat() + "Z"
        header = (
            "{"
            f'"exported_at": {json.dumps(exported_at)}, '
            f'"org_id": {org_id}, '
            f'"organization": {json.dumps(org_payload, default=str)}, '
            '"tables": {'
        )
        yield header.encode("utf-8")

        for table_idx, (table_name, fk_column) in enumerate(table_specs):
            if table_idx > 0:
                yield b", "
            yield f"{json.dumps(table_name)}: [".encode()
            stream_session = AsyncSessionLocal()
            try:
                result = await stream_session.stream(
                    text(
                        f"SELECT * FROM {table_name} WHERE {fk_column} = :org_id"
                    ).execution_options(yield_per=200),
                    {"org_id": org_id},
                )
                first_row = True
                async for row in result.mappings():
                    if not first_row:
                        yield b", "
                    first_row = False
                    yield json.dumps(
                        {k: _coerce(v) for k, v in row.items()},
                        default=str,
                    ).encode("utf-8")
            finally:
                await stream_session.close()
            yield b"]"

        yield b"}}"

    filename = f"org-{org_id}-export.json"
    return StreamingResponse(
        _stream_bundle(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/organizations/{org_id}/retention/run", status_code=202)
async def run_retention(
    org_id: int,
    _current_user: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Manual hook into the retention-sweep stub.

    The Month 4 cron job will call ``retention.run_retention_sweep`` on a
    schedule; this endpoint exists so admins can dry-run the call now and
    so the public API contract is stable before the cron lands.
    """
    # pylint: disable-next=import-outside-toplevel
    from app.services.retention import get_policy, run_retention_sweep

    deleted = await run_retention_sweep()
    return {"org_id": org_id, "policy": get_policy().__dict__, "deleted": deleted}
