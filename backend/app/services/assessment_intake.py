"""Assessment intake service — graduated tier evaluation for org cyber posture."""

from __future__ import annotations

from dataclasses import dataclass

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
# checker(snapshot) -> (met: bool, detail: str)


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


@dataclass
class IntakeSnapshot:
    """Plain-object view of an org's intake state — the pure evaluator's only input.

    Decoupling from the SQLAlchemy ORM lets us reuse the tier logic for the
    preview endpoint, where the "org" is a partially-filled form payload that
    has not been persisted yet.
    """

    name: str | None = None
    industry_label: str | None = None
    primary_state: str | None = None
    employee_range: str | None = None
    revenue_range: str | None = None
    security_controls: dict | None = None
    compliance_frameworks: list | None = None
    data_types: list | None = None
    vendor_count: int = 0
    domain_count: int = 0
    upload_count: int = 0


def _controls_answered(security_controls: dict | None) -> int:
    if not security_controls:
        return 0
    return sum(1 for v in security_controls.values() if v in ("yes", "no", "unsure"))


def _check_requirement(key: str, snap: IntakeSnapshot) -> tuple[bool, str]:
    """Return (met, detail) for a single requirement key against a snapshot."""
    controls_answered = _controls_answered(snap.security_controls)
    checks: dict[str, tuple[bool, str]] = {
        "name": (
            bool(snap.name and snap.name.strip()),
            snap.name or "Not set",
        ),
        "industry": (
            bool(snap.industry_label),
            snap.industry_label or "Not set",
        ),
        "state": (
            bool(snap.primary_state),
            snap.primary_state or "Not set",
        ),
        "employee_range": (
            bool(snap.employee_range),
            snap.employee_range or "Not set",
        ),
        "vendors": (
            snap.vendor_count >= 1,
            f"{snap.vendor_count} vendor(s) tracked",
        ),
        "domains": (
            snap.domain_count >= 1,
            f"{snap.domain_count} domain(s) registered",
        ),
        "security_controls": (
            controls_answered >= 1,
            f"{controls_answered} control(s) answered" if controls_answered else "Not started",
        ),
        "revenue": (
            bool(snap.revenue_range),
            snap.revenue_range or "Not set",
        ),
        "compliance_frameworks": (
            bool(snap.compliance_frameworks and len(snap.compliance_frameworks) > 0),
            (
                ", ".join(snap.compliance_frameworks[:3])
                if snap.compliance_frameworks
                else "Not set"
            ),
        ),
        "data_types": (
            bool(snap.data_types and len(snap.data_types) > 0),
            f"{len(snap.data_types)} type(s)" if snap.data_types else "Not set",
        ),
        "uploads": (
            snap.upload_count >= 1,
            f"{snap.upload_count} file(s) uploaded",
        ),
        "security_controls_depth": (
            controls_answered >= 8,
            f"{controls_answered}/16 controls answered",
        ),
    }
    return checks.get(key, (False, "Unknown requirement"))


def evaluate_intake_snapshot(snap: IntakeSnapshot) -> AssessmentIntakeResponse:
    """Pure tier evaluation against an in-memory snapshot. No DB access."""
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
            met, detail = _check_requirement(key, snap)
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


def _snapshot_from_org(
    org: Organization,
    vendor_count: int,
    domain_count: int,
    upload_count: int,
) -> IntakeSnapshot:
    return IntakeSnapshot(
        name=org.name,
        industry_label=org.industry_label,
        primary_state=org.primary_state,
        employee_range=org.employee_range,
        revenue_range=org.revenue_range,
        security_controls=org.security_controls,
        compliance_frameworks=org.compliance_frameworks,
        data_types=org.data_types,
        vendor_count=vendor_count,
        domain_count=domain_count,
        upload_count=upload_count,
    )


async def evaluate_intake(
    org: Organization,
    session: AsyncSession,
) -> AssessmentIntakeResponse:
    """Evaluate the org's assessment intake tier with graduated requirements."""
    vendor_count, domain_count, upload_count = await _fetch_counts(session, org.id)
    snap = _snapshot_from_org(org, vendor_count, domain_count, upload_count)
    return evaluate_intake_snapshot(snap)


async def evaluate_intake_preview(
    payload_snapshot: IntakeSnapshot,
    current_org: Organization | None,
    session: AsyncSession,
) -> AssessmentIntakeResponse:
    """Evaluate tier status for an unsaved intake form payload.

    Vendor/domain/upload counts come from the persisted org (if any) so that
    progress already earned isn't dropped when the user previews mid-form.
    Optimistic bumps for not-yet-synced primary_vendor / primary_domain are the
    caller's responsibility — pass the bumped counts on the snapshot.
    """
    if current_org is not None:
        vendor_count, domain_count, upload_count = await _fetch_counts(session, current_org.id)
        # Take the max so any optimistic bumps the caller applied for a typed-but-unsaved
        # primary_vendor / primary_domain win over the live count.
        payload_snapshot.vendor_count = max(payload_snapshot.vendor_count, vendor_count)
        payload_snapshot.domain_count = max(payload_snapshot.domain_count, domain_count)
        payload_snapshot.upload_count = max(payload_snapshot.upload_count, upload_count)
    return evaluate_intake_snapshot(payload_snapshot)
