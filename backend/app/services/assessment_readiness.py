"""Assessment readiness service — checks org data completeness."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.org_domain import OrgDomain
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.schemas.assessment_readiness import (
    AssessmentReadinessResponse,
    ReadinessItem,
)

# Readiness criteria: (key, label, required, checker, incomplete-hint)
# "checker" is a callable(org, counts) → (bool, detail_str)

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


async def evaluate_readiness(
    org: Organization,
    session: AsyncSession,
) -> AssessmentReadinessResponse:
    """Evaluate how complete an org's profile is for risk assessment."""

    org_id = org.id

    vendor_count, domain_count, upload_count = await _fetch_counts(session, org_id)

    # Security profile completeness checks
    has_controls = bool(org.security_controls and any(
        v in ("yes", "no", "unsure") for v in org.security_controls.values()
    ))
    controls_answered = sum(
        1 for v in (org.security_controls or {}).values() if v in ("yes", "no", "unsure")
    )

    has_compliance = bool(org.compliance_frameworks and len(org.compliance_frameworks) > 0)
    has_data_types = bool(org.data_types and len(org.data_types) > 0)

    items: list[ReadinessItem] = [
        ReadinessItem(
            key="org_name",
            label="Organization name",
            complete=bool(org.name and org.name.strip()),
            required=True,
            detail=org.name or "Not set",
        ),
        ReadinessItem(
            key="industry",
            label="Industry",
            complete=bool(org.industry_label),
            required=True,
            detail=org.industry_label or "Not set",
        ),
        ReadinessItem(
            key="state",
            label="Primary state",
            complete=bool(org.primary_state),
            required=True,
            detail=org.primary_state or "Not set",
        ),
        ReadinessItem(
            key="employee_range",
            label="Employee range",
            complete=bool(org.employee_range),
            required=True,
            detail=org.employee_range or "Not set",
        ),
        ReadinessItem(
            key="vendors",
            label="Technology stack",
            complete=vendor_count >= 1,
            required=True,
            detail=f"{vendor_count} vendor(s) tracked",
        ),
        ReadinessItem(
            key="domains",
            label="Organization domains",
            complete=domain_count >= 1,
            required=True,
            detail=f"{domain_count} domain(s) registered",
        ),
        ReadinessItem(
            key="security_controls",
            label="Security controls checklist",
            complete=has_controls,
            required=False,
            detail=f"{controls_answered} control(s) answered" if has_controls else "Not started",
        ),
        ReadinessItem(
            key="compliance_frameworks",
            label="Compliance frameworks",
            complete=has_compliance,
            required=False,
            detail=", ".join(org.compliance_frameworks[:3]) if has_compliance else "Not set",
        ),
        ReadinessItem(
            key="data_types",
            label="Data types handled",
            complete=has_data_types,
            required=False,
            detail=f"{len(org.data_types)} type(s)" if has_data_types else "Not set",
        ),
        ReadinessItem(
            key="revenue",
            label="Revenue range",
            complete=bool(org.revenue_range),
            required=False,
            detail=org.revenue_range or "Not set",
        ),
        ReadinessItem(
            key="uploads",
            label="Supporting documents",
            complete=upload_count >= 1,
            required=False,
            detail=f"{upload_count} file(s) uploaded",
        ),
    ]

    required_items = [i for i in items if i.required]
    all_items = items

    required_done = sum(1 for i in required_items if i.complete)
    total_done = sum(1 for i in all_items if i.complete)

    is_ready = required_done == len(required_items)

    readiness_pct = round((total_done / len(all_items)) * 100, 1) if all_items else 0.0

    if total_done == len(all_items):
        tier = "comprehensive"
    elif is_ready:
        tier = "good"
    else:
        tier = "minimal"

    next_steps = [
        _NEXT_STEP_MAP[i.key] for i in all_items if not i.complete and i.key in _NEXT_STEP_MAP
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
