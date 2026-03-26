"""Threat intelligence routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.db.engine import get_session
from app.db.models import CVE, KEV
from app.db.user import User

router = APIRouter()


@router.get("/high-risk")
async def high_risk_threats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role("viewer")),
) -> list[dict[str, object]]:
    """Return top high-risk CVEs by exploitation and CVSS score."""
    result = await session.execute(
        select(CVE, KEV)
        .outerjoin(KEV, KEV.cve_id == CVE.cve_id)
        .where(CVE.cvss_score.is_not(None))
        .order_by(desc(KEV.cve_id.is_not(None)), desc(CVE.cvss_score))
        .limit(10)
    )
    rows = result.all()

    return [
        {
            "cve_id": cve.cve_id,
            "cvss": cve.cvss_score,
            "exploited": kev is not None,
        }
        for cve, kev in rows
    ]
