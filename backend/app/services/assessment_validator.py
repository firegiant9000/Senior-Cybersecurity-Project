"""Assessment validation engine — evaluates org data quality and returns structured issues."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.org_domain import OrgDomain
from app.db.org_upload import OrgUpload
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.schemas.assessment_validation import AssessmentValidationResponse, ValidationIssueResponse

# Compliance → required data type keywords (case-insensitive substring match)
_COMPLIANCE_DATA_REQUIREMENTS: dict[str, list[str]] = {
    "HIPAA": ["phi", "health"],
    "PCI-DSS": ["payment", "card"],
}

_DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"
)


@dataclass
class _Issue:
    category: str
    severity: str
    field: str
    message: str
    suggestion: str | None = None


@dataclass
class _ValidationResult:
    issues: list[_Issue] = field(default_factory=list)

    def add(
        self,
        category: str,
        severity: str,
        field_name: str,
        message: str,
        suggestion: str | None = None,
    ) -> None:
        self.issues.append(
            _Issue(
                category=category,
                severity=severity,
                field=field_name,
                message=message,
                suggestion=suggestion,
            )
        )

    @property
    def score(self) -> float:
        pts = 100.0
        for issue in self.issues:
            if issue.severity == "error":
                pts -= 15
            elif issue.severity == "warning":
                pts -= 5
            else:
                pts -= 1
        return max(0.0, min(100.0, pts))

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


async def run_validation(
    org: Organization,
    session: AsyncSession,
) -> _ValidationResult:
    """Run all validation rules against the org and return a structured result."""
    result = _ValidationResult()

    vendors, domains, upload_count = await _fetch_data(session, org.id)

    _check_missing_fields(org, vendors, domains, result)
    _check_duplicate_vendors(vendors, result)
    _check_duplicate_domains(domains, result)
    _check_invalid_formats(vendors, domains, result)
    _check_conflicts(org, result)
    _check_quality(org, vendors, domains, upload_count, result)

    return result


async def _fetch_data(
    session: AsyncSession, org_id: int
) -> tuple[list[OrgVendor], list[OrgDomain], int]:
    vendor_rows = (
        await session.execute(select(OrgVendor).where(OrgVendor.org_id == org_id))
    ).scalars().all()

    domain_rows = (
        await session.execute(select(OrgDomain).where(OrgDomain.org_id == org_id))
    ).scalars().all()

    upload_count = (
        await session.execute(
            select(func.count(OrgUpload.id)).where(OrgUpload.org_id == org_id)
        )
    ).scalar_one()

    return list(vendor_rows), list(domain_rows), int(upload_count or 0)


# ── Rule categories ────────────────────────────────────────────────────────────


def _check_missing_fields(
    org: Organization,
    vendors: list[OrgVendor],
    domains: list[OrgDomain],
    result: _ValidationResult,
) -> None:
    if not org.name or not org.name.strip():
        result.add(
            "missing_field", "error", "org_name",
            "Organization name is missing.",
            "Set your organization name in Settings > Company Profile.",
        )
    if not org.industry_label:
        result.add(
            "missing_field", "error", "industry",
            "Industry is not set.",
            "Select your industry in Settings or during onboarding.",
        )
    if not org.primary_state:
        result.add(
            "missing_field", "error", "primary_state",
            "Primary state is not set.",
            "Set your primary state in Settings or during onboarding.",
        )
    if not org.employee_range:
        result.add(
            "missing_field", "error", "employee_range",
            "Employee range is not set.",
            "Set your employee range in Settings or during onboarding.",
        )
    if not vendors:
        result.add(
            "missing_field", "error", "vendors",
            "No vendors in your technology stack.",
            "Add at least one vendor in Settings > Technology Stack.",
        )
    if not domains:
        result.add(
            "missing_field", "error", "domains",
            "No domains registered.",
            "Add at least one domain in Settings > Organization Domains.",
        )
    if not org.revenue_range:
        result.add(
            "missing_field", "warning", "revenue_range",
            "Revenue range is not set.",
            "Provide your revenue range for more accurate loss projections.",
        )
    controls = org.security_controls or {}
    answered_controls = [v for v in controls.values() if v in ("yes", "no", "unsure")]
    if not answered_controls:
        result.add(
            "missing_field", "warning", "security_controls",
            "No security controls have been answered.",
            "Complete the security controls checklist in Organization Profile.",
        )
    if not org.compliance_frameworks:
        result.add(
            "missing_field", "info", "compliance_frameworks",
            "No compliance frameworks selected.",
            "Select applicable compliance frameworks in Organization Profile.",
        )
    if not org.data_types:
        result.add(
            "missing_field", "info", "data_types",
            "No data types specified.",
            "Specify the types of data your organization handles in Organization Profile.",
        )


def _check_duplicate_vendors(
    vendors: list[OrgVendor],
    result: _ValidationResult,
) -> None:
    names = [v.vendor_name for v in vendors]

    # Case-duplicate check
    seen: dict[str, str] = {}
    for name in names:
        lower = name.lower()
        if lower in seen and seen[lower] != name:
            result.add(
                "duplicate", "warning", "vendors",
                f'Possible duplicate vendors: "{seen[lower]}" and "{name}" differ only in casing.',
                "Remove the duplicate or standardize casing.",
            )
        else:
            seen[lower] = name

    # Near-duplicate check (Levenshtein-like via difflib, skip pairs already flagged as case-dupes)
    lowered = [n.lower() for n in names]
    reported: set[frozenset[str]] = set()
    for i in range(len(lowered)):
        for j in range(i + 1, len(lowered)):
            a, b = lowered[i], lowered[j]
            if a == b:
                continue
            pair = frozenset({a, b})
            if pair in reported:
                continue
            # Skip pairs with large length difference — quick exit
            if abs(len(a) - len(b)) > 3:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            # ratio > 0.85 with length ≥ 3 catches most 1-2 char edits
            if ratio > 0.85 and len(a) >= 3:
                reported.add(pair)
                result.add(
                    "duplicate", "warning", "vendors",
                    f'Possibly similar vendors: "{names[i]}" and "{names[j]}".',
                    "Review and remove duplicates to keep your stack accurate.",
                )


def _check_duplicate_domains(
    domains: list[OrgDomain],
    result: _ValidationResult,
) -> None:
    seen: dict[str, str] = {}
    for d in domains:
        lower = d.domain_name.lower()
        if lower in seen and seen[lower] != d.domain_name:
            result.add(
                "duplicate", "warning", "domains",
                f'Possible duplicate domains: "{seen[lower]}" and "{d.domain_name}" differ only in casing.',
                "Remove the duplicate domain.",
            )
        else:
            seen[lower] = d.domain_name


def _check_invalid_formats(
    vendors: list[OrgVendor],
    domains: list[OrgDomain],
    result: _ValidationResult,
) -> None:
    for d in domains:
        if not _DOMAIN_RE.match(d.domain_name):
            result.add(
                "invalid_format", "error", "domains",
                f'Domain "{d.domain_name}" does not appear to be a valid domain name.',
                "Remove and re-add the domain using the correct format (e.g. example.com).",
            )

    for v in vendors:
        name = v.vendor_name
        if name != name.strip() or "  " in name:
            result.add(
                "invalid_format", "warning", "vendors",
                f'Vendor "{name}" has leading/trailing or consecutive spaces.',
                "Edit the vendor name to remove extra whitespace.",
            )


def _check_conflicts(
    org: Organization,
    result: _ValidationResult,
) -> None:
    frameworks = [f.upper() for f in (org.compliance_frameworks or [])]
    data_types_lower = [dt.lower() for dt in (org.data_types or [])]

    for framework, required_keywords in _COMPLIANCE_DATA_REQUIREMENTS.items():
        if framework not in frameworks:
            continue
        matched = any(
            kw in dt for dt in data_types_lower for kw in required_keywords
        )
        if not matched:
            result.add(
                "conflict", "warning", "compliance_frameworks",
                f"{framework} is selected but no matching data type is specified.",
                f"Add the relevant data type for {framework} or remove the framework if it doesn't apply.",
            )


def _check_quality(
    org: Organization,
    vendors: list[OrgVendor],
    domains: list[OrgDomain],
    upload_count: int,
    result: _ValidationResult,
) -> None:
    controls = org.security_controls or {}
    answered = [v for v in controls.values() if v in ("yes", "no", "unsure")]
    if answered and all(v == "unsure" for v in answered):
        result.add(
            "quality", "warning", "security_controls",
            "All security controls are answered 'unsure', which provides no signal for risk assessment.",
            "Review the controls and update answers where you have definitive information.",
        )

    if len(vendors) == 1:
        result.add(
            "quality", "info", "vendors",
            "Only one vendor is tracked — your technology stack may be incomplete.",
            "Add more vendors to get a more accurate risk assessment.",
        )

    if upload_count == 0:
        result.add(
            "quality", "info", "uploads",
            "No supporting documents have been uploaded.",
            "Upload any relevant documents (policies, audit reports) in Settings > File Uploads.",
        )


def build_response(result: _ValidationResult) -> AssessmentValidationResponse:
    issues_out = [
        ValidationIssueResponse(
            category=i.category,
            severity=i.severity,
            field=i.field,
            message=i.message,
            suggestion=i.suggestion,
        )
        for i in result.issues
    ]
    counts = {"error": 0, "warning": 0, "info": 0}
    for i in result.issues:
        if i.severity in counts:
            counts[i.severity] += 1
    return AssessmentValidationResponse(
        issues=issues_out,
        score=result.score,
        passed=result.passed,
        issue_counts=counts,
    )
