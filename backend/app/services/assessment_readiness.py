"""Assessment readiness service — checks org data completeness.

Delegates to the graduated intake tier system and maps back to the
legacy three-tier format (minimal / good / comprehensive) for backward
compatibility with existing consumers.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.org_domain import OrgDomain
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.schemas.assessment_intake import AssessmentTier
from app.schemas.assessment_readiness import (
    AssessmentReadinessResponse,
    ReadinessItem,
)

_NEXT_STEP_MAP: dict[str, str] = {
    "org_name": "Set your organization name in Settings > Company Profile.",
    "industry": "Select your industry during onboarding or in Settings.",
    "state": "Set your primary state during onboarding or in Settings.",
    "employee_range": "Set your employee range during onboarding or in Settings.",
    "vendors": "Add at least one vendor in Settings > Technology Stack.",
    "domains": "Add at least one domain in Settings > Organization Domains.",
    "security_controls": "Complete the security controls checklist in Organization Profile.",
    "compliance_frameworks": "Select your compliance frameworks in Organization Profile.",
    "data_types": "Specify data types your organization handles in Organization Profile.",
    "revenue": "Provide your revenue range for more accurate loss projections.",
    "uploads": "Upload at least one supporting document in Settings > File Uploads.",
}

# Map graduated intake tiers → legacy readiness tier names
_TIER_TO_LEGACY: dict[AssessmentTier, str] = {
    AssessmentTier.INCOMPLETE: "minimal",
    AssessmentTier.BASIC: "minimal",
    AssessmentTier.ENHANCED: "good",
    AssessmentTier.COMPREHENSIVE: "comprehensive",
}


async def evaluate_readiness(
    org: Organization,
    session: AsyncSession,
) -> AssessmentReadinessResponse:
    """Evaluate how complete an org's profile is for risk assessment.

    Delegates tier computation to the intake service, then maps the result
    back to the legacy readiness response format.
    """
    from app.services.assessment_intake import evaluate_intake

    intake = await evaluate_intake(org, session)

    # Flatten all tier requirements into ReadinessItem list.
    # Basic tier reqs are "required", Enhanced/Comprehensive are "optional".
    items: list[ReadinessItem] = []
    seen_keys: set[str] = set()

    for td in intake.tiers:
        is_required = td.tier == AssessmentTier.BASIC
        for req in td.requirements:
            if req.key in seen_keys:
                continue
            seen_keys.add(req.key)
            items.append(
                ReadinessItem(
                    key=req.key,
                    label=req.label,
                    complete=req.met,
                    required=is_required,
                    detail=req.detail,
                )
            )

    required_items = [i for i in items if i.required]
    required_done = sum(1 for i in required_items if i.complete)
    total_done = sum(1 for i in items if i.complete)
    is_ready = required_done == len(required_items)
    readiness_pct = round((total_done / len(items)) * 100, 1) if items else 0.0

    tier = _TIER_TO_LEGACY[intake.current_tier]

    next_steps = [
        _NEXT_STEP_MAP[i.key] for i in items if not i.complete and i.key in _NEXT_STEP_MAP
    ]

    return AssessmentReadinessResponse(
        is_ready=is_ready,
        readiness_pct=readiness_pct,
        tier=tier,
        items=items,
        next_steps=next_steps,
    )


async def _fetch_counts(session: AsyncSession, org_id: int) -> tuple[int, int, int]:
    """Return (vendor_count, domain_count, upload_count) in a single round-trip."""
    result = await session.execute(
        select(
            select(func.count(OrgVendor.id))
            .where(OrgVendor.org_id == org_id)
            .correlate(None)
            .scalar_subquery()
            .label("vendor_count"),
            select(func.count(OrgDomain.id))
            .where(OrgDomain.org_id == org_id)
            .correlate(None)
            .scalar_subquery()
            .label("domain_count"),
            select(func.count(OrgUpload.id))
            .where(OrgUpload.org_id == org_id)
            .correlate(None)
            .scalar_subquery()
            .label("upload_count"),
        )
    )
    row = result.one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
