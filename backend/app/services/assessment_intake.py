"""Assessment intake service — graduated tier evaluation for org cyber posture."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import Organization
from app.schemas.assessment_intake import (
    AssessmentIntakeResponse,
    AssessmentTier,
    TierDefinition,
    TierRequirement,
)
from app.services.assessment_readiness import _fetch_counts

# ── Tier requirement specs ──────────────────────────────────────────
# Each tier lists (key, label, checker) tuples.
# checker(org, counts) -> (met: bool, detail: str)

_TIER_SPECS: list[tuple[AssessmentTier, str, str, list[str], list[tuple[str, str, object]]]] = []

# Build tier specs inline for clarity:

_BASIC_REQS: list[tuple[str, str]] = [
    ("name", "Organization name"),
    ("industry", "Industry"),
    ("state", "Primary state"),
    ("employee_range", "Employee range"),
]

_ENHANCED_REQS: list[tuple[str, str]] = [
    ("vendors", "At least 1 vendor"),
    ("domains", "At least 1 domain"),
    ("security_controls", "Security controls started"),
]

_COMPREHENSIVE_REQS: list[tuple[str, str]] = [
    ("revenue", "Revenue range"),
    ("compliance_frameworks", "Compliance frameworks"),
    ("data_types", "Data types handled"),
    ("uploads", "At least 1 upload"),
    ("security_controls_depth", "8+ security controls answered"),
]

_TIER_UNLOCKS: dict[AssessmentTier, list[str]] = {
    AssessmentTier.BASIC: [
        "Risk score",
        "Loss projection",
        "SMB Risk Advisor",
        "Executive summary",
    ],
    AssessmentTier.ENHANCED: [
        "Findings report",
        "Vendor alerts",
        "Domain checks",
        "AI summary",
    ],
    AssessmentTier.COMPREHENSIVE: [
        "Full confidence scores",
        "Compliance-aware findings",
        "Detailed loss projections",
    ],
}

_TIER_META: list[tuple[AssessmentTier, str, str]] = [
    (
        AssessmentTier.BASIC,
        "Basic Risk Profile",
        "Minimum information needed for a baseline risk assessment.",
    ),
    (
        AssessmentTier.ENHANCED,
        "Enhanced Assessment",
        "Adds vendor and domain intelligence for actionable findings.",
    ),
    (
        AssessmentTier.COMPREHENSIVE,
        "Comprehensive Posture",
        "Full organizational context for highest-confidence analysis.",
    ),
]


def _check_requirement(
    key: str,
    org: Organization,
    vendor_count: int,
    domain_count: int,
    upload_count: int,
    controls_answered: int,
) -> tuple[bool, str]:
    """Return (met, detail) for a single requirement key."""
    checks: dict[str, tuple[bool, str]] = {
        "name": (
            bool(org.name and org.name.strip()),
            org.name or "Not set",
        ),
        "industry": (
            bool(org.industry_label),
            org.industry_label or "Not set",
        ),
        "state": (
            bool(org.primary_state),
            org.primary_state or "Not set",
        ),
        "employee_range": (
            bool(org.employee_range),
            org.employee_range or "Not set",
        ),
        "vendors": (
            vendor_count >= 1,
            f"{vendor_count} vendor(s) tracked",
        ),
        "domains": (
            domain_count >= 1,
            f"{domain_count} domain(s) registered",
        ),
        "security_controls": (
            controls_answered >= 1,
            f"{controls_answered} control(s) answered" if controls_answered else "Not started",
        ),
        "revenue": (
            bool(org.revenue_range),
            org.revenue_range or "Not set",
        ),
        "compliance_frameworks": (
            bool(org.compliance_frameworks and len(org.compliance_frameworks) > 0),
            (", ".join(org.compliance_frameworks[:3]) if org.compliance_frameworks else "Not set"),
        ),
        "data_types": (
            bool(org.data_types and len(org.data_types) > 0),
            f"{len(org.data_types)} type(s)" if org.data_types else "Not set",
        ),
        "uploads": (
            upload_count >= 1,
            f"{upload_count} file(s) uploaded",
        ),
        "security_controls_depth": (
            controls_answered >= 8,
            f"{controls_answered}/16 controls answered",
        ),
    }
    return checks.get(key, (False, "Unknown requirement"))


async def evaluate_intake(
    org: Organization,
    session: AsyncSession,
) -> AssessmentIntakeResponse:
    """Evaluate the org's assessment intake tier with graduated requirements."""

    vendor_count, domain_count, upload_count = await _fetch_counts(session, org.id)

    controls_answered = sum(
        1 for v in (org.security_controls or {}).values() if v in ("yes", "no", "unsure")
    )

    # Build requirement lists per tier
    tier_req_keys: list[tuple[AssessmentTier, list[tuple[str, str]]]] = [
        (AssessmentTier.BASIC, _BASIC_REQS),
        (AssessmentTier.ENHANCED, _ENHANCED_REQS),
        (AssessmentTier.COMPREHENSIVE, _COMPREHENSIVE_REQS),
    ]

    tier_definitions: list[TierDefinition] = []
    current_tier = AssessmentTier.INCOMPLETE

    for tier_enum, label, description in _TIER_META:
        req_specs = next(reqs for t, reqs in tier_req_keys if t == tier_enum)
        requirements: list[TierRequirement] = []

        for key, req_label in req_specs:
            met, detail = _check_requirement(
                key, org, vendor_count, domain_count, upload_count, controls_answered
            )
            requirements.append(TierRequirement(key=key, label=req_label, met=met, detail=detail))

        all_met = all(r.met for r in requirements)

        tier_definitions.append(
            TierDefinition(
                tier=tier_enum,
                label=label,
                description=description,
                requirements=requirements,
                all_met=all_met,
                unlocks=_TIER_UNLOCKS[tier_enum],
            )
        )

    # Determine current tier: highest tier where all requirements (and all prior tiers) are met
    for td in tier_definitions:
        if td.all_met:
            current_tier = td.tier
        else:
            break

    # Determine next tier and progress toward it
    tier_order = [
        AssessmentTier.INCOMPLETE,
        AssessmentTier.BASIC,
        AssessmentTier.ENHANCED,
        AssessmentTier.COMPREHENSIVE,
    ]
    current_idx = tier_order.index(current_tier)

    next_tier: AssessmentTier | None = None
    next_tier_progress = 0.0
    fields_to_advance: list[str] = []

    if current_idx < len(tier_order) - 1:
        next_tier = tier_order[current_idx + 1]
        next_td = next(td for td in tier_definitions if td.tier == next_tier)
        total_reqs = len(next_td.requirements)
        met_reqs = sum(1 for r in next_td.requirements if r.met)
        next_tier_progress = round((met_reqs / total_reqs) * 100, 1) if total_reqs else 0.0
        fields_to_advance = [r.key for r in next_td.requirements if not r.met]

    return AssessmentIntakeResponse(
        current_tier=current_tier,
        tiers=tier_definitions,
        next_tier=next_tier,
        next_tier_progress=next_tier_progress,
        fields_to_advance=fields_to_advance,
    )
