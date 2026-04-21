"""Findings Engine — synthesizes platform signals into structured, actionable findings.

Orchestration flow:
  1. Gather existing signal sources concurrently (risk score, vendor alerts,
     assessment readiness, loss projection).
  2. Run domain checks concurrently (Tier 1: DNS/HTTP/SSL; Tier 2: crt.sh/HIBP).
  3. Analyze each signal category and emit Finding objects.
  4. Return a FindingsReport sorted by severity.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import INDUSTRY_TO_IC3_SECTOR, IndustryLabel
from app.db.org_domain import OrgDomain
from app.db.organization import Organization
from app.ingestors.ic3_real import ATTACK_SECTOR_WEIGHTS
from app.schemas.findings import Finding, FindingsReport, FindingsSummary
from app.services.assessment_readiness import evaluate_readiness
from app.services.disclaimers import DisclaimerContext, get_disclaimer
from app.services.domain_checks import (
    DnsCheckResult,
    HttpHeaderResult,
    OtxResult,
    ShodanHostResult,
    SslCheckResult,
    TechFingerprintResult,
    run_tier1_checks,
    run_tier2_checks,
)
from app.services.risk_scoring import calculate_smb_risk_score
from app.services.vendor_alerts import VendorAlertService

logger = logging.getLogger(__name__)

# Severity sort order for final report
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Threshold: sector attack weight at or above this is "significant exposure"
_SECTOR_EXPOSURE_THRESHOLD = 0.15


def _severity_score(label: str, weight: float = 0.5) -> float:
    """Convert a severity label + optional weight into a 0-100 numeric score.

    Each label maps to a base range. The weight (0.0-1.0) positions the score
    within that range for finer granularity:
        critical: 80-100
        high:     60-79
        medium:   40-59
        low:      20-39
        info:     0-19
    """
    ranges = {
        "critical": (80, 100),
        "high": (60, 79),
        "medium": (40, 59),
        "low": (20, 39),
        "info": (0, 19),
    }
    lo, hi = ranges.get(label, (40, 59))
    w = max(0.0, min(1.0, weight))
    return round(lo + (hi - lo) * w, 1)


def _label_from_score(score: float) -> str:
    """Derive severity label from a numeric score."""
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "info"


def _finding_id(*parts: str) -> str:
    """Deterministic 12-char hex ID for dedup."""
    key = "|".join(parts)
    return hashlib.sha1(key.encode()).hexdigest()[:12]  # noqa: S324


# ---------------------------------------------------------------------------
# Threat exposure findings
# ---------------------------------------------------------------------------


def _threat_exposure_from_sector(
    ic3_sector: str | None,
    industry_label: str | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if not ic3_sector:
        return findings

    # Build {attack_type: weight} for this sector
    sector_weights: dict[str, float] = {}
    for attack_type, sector_list in ATTACK_SECTOR_WEIGHTS.items():
        for sector, weight in sector_list:
            if sector == ic3_sector:
                sector_weights[attack_type] = weight
                break

    high_exposure = [(a, w) for a, w in sector_weights.items() if w >= _SECTOR_EXPOSURE_THRESHOLD]
    high_exposure.sort(key=lambda x: x[1], reverse=True)

    for attack_type, weight in high_exposure:
        pct = round(weight * 100)
        severity = "high" if weight >= 0.20 else "medium"
        # Scale score within severity range by how far above threshold
        score_weight = min(1.0, (weight - _SECTOR_EXPOSURE_THRESHOLD) / 0.25)
        findings.append(
            Finding(
                id=_finding_id("threat_sector", ic3_sector, attack_type),
                finding_type="threat_exposure",
                severity=severity,
                severity_score=_severity_score(severity, score_weight),
                title=f"{industry_label or ic3_sector} is a top target for {attack_type}",
                description=(
                    f"FBI IC3 data and industry research indicate that {ic3_sector} organizations "
                    f"account for approximately {pct}% of {attack_type} incidents. "
                    f"Organizations in this sector should prioritize defenses against this attack type."
                ),
                evidence={"sector": ic3_sector, "attack_type": attack_type, "weight": weight},
                source="ic3_sector_weights",
                affected_assets=[ic3_sector],
            )
        )

    return findings


def _threat_exposure_from_dns(domain: str, dns: DnsCheckResult) -> list[Finding]:
    findings: list[Finding] = []
    if dns.error:
        return findings

    if not dns.spf_found:
        findings.append(
            Finding(
                id=_finding_id("dns_no_spf", domain),
                finding_type="threat_exposure",
                severity="high",
                severity_score=_severity_score("high", 0.7),
                title=f"No SPF record found for {domain}",
                description=(
                    f"The domain {domain} has no SPF (Sender Policy Framework) TXT record. "
                    "Without SPF, attackers can send emails that appear to come from your domain, "
                    "enabling phishing and impersonation attacks against your partners and customers."
                ),
                evidence={"domain": domain, "spf_found": False},
                source="dns_checks",
                affected_assets=[domain],
            )
        )

    if not dns.dmarc_found:
        findings.append(
            Finding(
                id=_finding_id("dns_no_dmarc", domain),
                finding_type="threat_exposure",
                severity="high",
                severity_score=_severity_score("high", 0.8),
                title=f"No DMARC record found for {domain}",
                description=(
                    f"The domain {domain} has no DMARC policy. Without DMARC, spoofed emails "
                    "from your domain will be delivered to recipients with no automated rejection. "
                    "DMARC with a 'reject' or 'quarantine' policy prevents email spoofing."
                ),
                evidence={"domain": domain, "dmarc_found": False},
                source="dns_checks",
                affected_assets=[domain],
            )
        )
    elif dns.dmarc_policy in ("none", None):
        findings.append(
            Finding(
                id=_finding_id("dns_dmarc_none", domain),
                finding_type="threat_exposure",
                severity="medium",
                severity_score=_severity_score("medium", 0.6),
                title=f"DMARC policy is set to 'none' for {domain}",
                description=(
                    f"DMARC is configured for {domain} but the policy is 'p=none', which only "
                    "monitors email traffic without rejecting or quarantining spoofed messages. "
                    "Upgrade to 'p=quarantine' or 'p=reject' to actively block spoofed emails."
                ),
                evidence={"domain": domain, "dmarc_policy": dns.dmarc_policy},
                source="dns_checks",
                affected_assets=[domain],
            )
        )

    return findings


def _threat_exposure_from_ssl(domain: str, ssl_result: SslCheckResult) -> list[Finding]:
    findings: list[Finding] = []
    if not ssl_result.reachable:
        return findings

    if ssl_result.self_signed:
        findings.append(
            Finding(
                id=_finding_id("ssl_self_signed", domain),
                finding_type="threat_exposure",
                severity="high",
                severity_score=_severity_score("high", 0.6),
                title=f"Self-signed SSL certificate detected on {domain}",
                description=(
                    f"The domain {domain} is serving a self-signed TLS certificate. "
                    "Self-signed certificates are not trusted by browsers and may indicate "
                    "a misconfiguration or a man-in-the-middle interception. Replace with a "
                    "certificate from a trusted Certificate Authority."
                ),
                evidence={"domain": domain, "self_signed": True, "issuer": ssl_result.issuer},
                source="ssl_checks",
                affected_assets=[domain],
            )
        )
    elif ssl_result.days_until_expiry is not None and ssl_result.days_until_expiry <= 30:
        severity = "critical" if ssl_result.days_until_expiry <= 7 else "high"
        # Urgency increases as expiry approaches: 0 days → weight 1.0, 30 days → weight 0.2
        expiry_weight = 1.0 - (ssl_result.days_until_expiry / 30) * 0.8
        findings.append(
            Finding(
                id=_finding_id("ssl_expiring", domain),
                finding_type="threat_exposure",
                severity=severity,
                severity_score=_severity_score(severity, expiry_weight),
                title=f"SSL certificate for {domain} expires in {ssl_result.days_until_expiry} days",
                description=(
                    f"The TLS certificate for {domain} expires on "
                    f"{ssl_result.expiry.strftime('%Y-%m-%d') if ssl_result.expiry else 'unknown'}. "
                    "An expired certificate causes browser warnings and prevents secure connections, "
                    "disrupting operations and eroding customer trust."
                ),
                evidence={
                    "domain": domain,
                    "days_until_expiry": ssl_result.days_until_expiry,
                    "expiry": ssl_result.expiry.isoformat() if ssl_result.expiry else None,
                    "issuer": ssl_result.issuer,
                },
                source="ssl_checks",
                affected_assets=[domain],
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Vendor exposure findings
# ---------------------------------------------------------------------------


def _vendor_exposure_findings(  # noqa: C901
    vendor_alerts_data: dict,
) -> list[Finding]:
    findings: list[Finding] = []

    severity_breakdown = vendor_alerts_data.get("severity_breakdown", {})
    total_matched = vendor_alerts_data.get("total_matched", 0)
    unmatched_vendors = vendor_alerts_data.get("unmatched_vendors", [])
    reason = vendor_alerts_data.get("reason")

    if reason == "no_vendors":
        return findings  # handled in data_gap findings

    if total_matched == 0:
        return findings  # no CVE exposure

    critical_count = severity_breakdown.get("critical", 0)
    high_count = severity_breakdown.get("high", 0)

    if critical_count > 0:
        # More critical CVEs → higher score within critical range
        crit_weight = min(1.0, critical_count / 10)
        findings.append(
            Finding(
                id=_finding_id("vendor_critical_cves", str(critical_count)),
                finding_type="vendor_exposure",
                severity="critical",
                severity_score=_severity_score("critical", crit_weight),
                title=f"{critical_count} critical known-exploited CVE(s) match your tech stack",
                description=(
                    f"CISA's Known Exploited Vulnerabilities catalog contains {critical_count} "
                    f"critical-severity CVE(s) that match vendors in your technology stack. "
                    "These vulnerabilities have confirmed active exploitation in the wild "
                    "and require immediate patching."
                ),
                evidence={"critical_count": critical_count, "total_matched": total_matched},
                source="kev_vendor_match",
                affected_assets=[],
            )
        )

    if high_count > 0:
        high_weight = min(1.0, high_count / 15)
        findings.append(
            Finding(
                id=_finding_id("vendor_high_cves", str(high_count)),
                finding_type="vendor_exposure",
                severity="high",
                severity_score=_severity_score("high", high_weight),
                title=f"{high_count} high-severity exploited CVE(s) match your tech stack",
                description=(
                    f"CISA KEV contains {high_count} high-severity CVE(s) affecting vendors in your "
                    "stack. While less severe than critical, these are actively exploited and "
                    "should be patched on an accelerated schedule."
                ),
                evidence={"high_count": high_count, "total_matched": total_matched},
                source="kev_vendor_match",
                affected_assets=[],
            )
        )

    # Check for upcoming CISA deadlines from top items
    items = vendor_alerts_data.get("items", [])
    upcoming_deadline_vendors: list[str] = []
    now = datetime.now(UTC)
    for item in items:
        due_date = item.get("due_date")
        if due_date:
            try:
                if isinstance(due_date, str):
                    due_dt = datetime.fromisoformat(due_date)
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=UTC)
                else:
                    due_dt = due_date
                days_left = (due_dt - now).days
                if 0 <= days_left <= 30:
                    upcoming_deadline_vendors.append(item.get("vendor_name", ""))
            except (ValueError, TypeError):
                pass

    if upcoming_deadline_vendors:
        count = len(upcoming_deadline_vendors)
        findings.append(
            Finding(
                id=_finding_id("vendor_cisa_deadline", str(count)),
                finding_type="vendor_exposure",
                severity="high",
                severity_score=_severity_score("high", 0.8),
                title=f"{count} vendor CVE(s) have CISA remediation deadlines within 30 days",
                description=(
                    f"CISA requires federal agencies to remediate {count} CVE(s) affecting your "
                    "vendor stack within 30 days. While this mandate applies to federal agencies, "
                    "these deadlines indicate the highest-priority vulnerabilities requiring "
                    "immediate attention."
                ),
                evidence={"count": count, "vendors": list(set(upcoming_deadline_vendors))},
                source="kev_vendor_match",
                affected_assets=list(set(upcoming_deadline_vendors)),
            )
        )

    # Positive signal for unmatched vendors
    if unmatched_vendors:
        findings.append(
            Finding(
                id=_finding_id("vendor_no_kev_match", ",".join(sorted(unmatched_vendors))),
                finding_type="vendor_exposure",
                severity="info",
                severity_score=_severity_score("info", 0.3),
                title=f"{len(unmatched_vendors)} vendor(s) have no known exploited vulnerabilities",
                description=(
                    f"The following vendors in your stack have no entries in CISA KEV: "
                    f"{', '.join(unmatched_vendors[:5])}{'...' if len(unmatched_vendors) > 5 else ''}. "
                    "This is a positive signal — it does not mean these products are vulnerability-free, "
                    "but they have not been actively exploited in a way that reached CISA's catalog."
                ),
                evidence={"unmatched_vendors": unmatched_vendors},
                source="kev_vendor_match",
                affected_assets=unmatched_vendors,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Data gap findings
# ---------------------------------------------------------------------------


def _data_gap_findings(readiness_data: dict) -> list[Finding]:
    findings: list[Finding] = []

    items = readiness_data.get("items", [])
    tier = readiness_data.get("tier", "minimal")

    item_impact: dict[str, str] = {
        "org_name": "accurate org identification in reports",
        "industry": "sector-specific threat exposure analysis",
        "state": "geographic IC3 loss projection data",
        "employee_range": "size-adjusted risk scoring and loss estimates",
        "vendors": "vendor CVE matching against CISA KEV",
        "domains": "DNS, HTTP header, and SSL security checks",
        "revenue": "more accurate annual loss projections",
        "uploads": "document-based context for findings",
        "security_controls": "CIS IG1 baseline scoring and control gap analysis",
        "compliance_frameworks": "regulatory compliance gap detection and industry-specific findings",
        "data_types": "data-type-to-framework mapping and regulatory exposure analysis",
    }

    incomplete_required = [i for i in items if not i.get("complete") and i.get("required")]
    incomplete_optional = [i for i in items if not i.get("complete") and not i.get("required")]

    for item in incomplete_required:
        key = item.get("key", "")
        label = item.get("label", key)
        impact = item_impact.get(key, "complete risk assessment")
        findings.append(
            Finding(
                id=_finding_id("data_gap_required", key),
                finding_type="data_gap",
                severity="medium",
                severity_score=_severity_score("medium", 0.5),
                title=f"Required profile field missing: {label}",
                description=(
                    f"'{label}' is not set in your organization profile. "
                    f"This field is required for {impact}. "
                    "Complete your profile to unlock a fuller risk assessment."
                ),
                evidence={"key": key, "label": label, "required": True},
                source="assessment_readiness",
                affected_assets=[],
            )
        )

    for item in incomplete_optional:
        key = item.get("key", "")
        label = item.get("label", key)
        impact = item_impact.get(key, "assessment accuracy")
        findings.append(
            Finding(
                id=_finding_id("data_gap_optional", key),
                finding_type="data_gap",
                severity="low",
                severity_score=_severity_score("low", 0.4),
                title=f"Optional profile field missing: {label}",
                description=(f"'{label}' is not provided. Adding it improves {impact}."),
                evidence={"key": key, "label": label, "required": False},
                source="assessment_readiness",
                affected_assets=[],
            )
        )

    if tier == "minimal":
        findings.append(
            Finding(
                id=_finding_id("data_gap_tier_minimal"),
                finding_type="data_gap",
                severity="high",
                severity_score=_severity_score("high", 0.5),
                title="Assessment is incomplete — findings have limited accuracy",
                description=(
                    "Your organization profile is missing required fields. "
                    "The findings in this report are based on partial data and may not "
                    "reflect your actual risk posture. Complete your profile to get a "
                    "full, accurate assessment."
                ),
                evidence={"tier": tier},
                source="assessment_readiness",
                affected_assets=[],
            )
        )

    return findings


# ---------------------------------------------------------------------------
# HTTP header findings (recommended_action)
# ---------------------------------------------------------------------------


def _recommended_from_http_headers(domain: str, http: HttpHeaderResult) -> list[Finding]:
    findings: list[Finding] = []
    if not http.reachable:
        return findings

    missing: list[tuple[str, str, str]] = []
    if not http.has_hsts:
        missing.append(
            (
                "Strict-Transport-Security",
                "forces browsers to use HTTPS exclusively",
                "hsts",
            )
        )
    if not http.has_csp:
        missing.append(
            (
                "Content-Security-Policy",
                "restricts resource loading to prevent XSS attacks",
                "csp",
            )
        )
    if not http.has_x_frame_options:
        missing.append(
            (
                "X-Frame-Options",
                "prevents clickjacking by blocking iframe embedding",
                "xframe",
            )
        )
    if not http.has_x_content_type:
        missing.append(
            (
                "X-Content-Type-Options",
                "prevents MIME-type sniffing attacks",
                "xcontent",
            )
        )
    if not http.has_permissions_policy:
        missing.append(
            (
                "Permissions-Policy",
                "controls browser feature access (camera, microphone, etc.)",
                "permissions",
            )
        )

    if not missing:
        return findings

    header_names = [m[0] for m in missing]
    descriptions = [m[1] for m in missing]
    severity = "medium" if len(missing) >= 3 else "low"
    # Scale by how many headers are missing (out of 5 possible)
    header_weight = len(missing) / 5

    findings.append(
        Finding(
            id=_finding_id("http_missing_headers", domain, ",".join(m[2] for m in missing)),
            finding_type="recommended_action",
            severity=severity,
            severity_score=_severity_score(severity, header_weight),
            title=f"{len(missing)} security header(s) missing on {domain}",
            description=(
                f"The following HTTP security headers are absent from {domain}: "
                f"{', '.join(header_names)}. "
                f"These headers {'; '.join(descriptions[:2])}. "
                "Adding them is a low-effort, high-impact hardening step."
            ),
            evidence={
                "domain": domain,
                "missing_headers": header_names,
                "status_code": http.status_code,
            },
            source="http_header_checks",
            affected_assets=[domain],
        )
    )

    return findings


# ---------------------------------------------------------------------------
# crt.sh subdomain findings
# ---------------------------------------------------------------------------


def _recommended_from_crtsh(domain: str, crt: CrtShResult) -> list[Finding]:  # noqa: F821
    findings: list[Finding] = []
    if crt.error or not crt.subdomains:
        return findings

    count = len(crt.subdomains)
    if count >= 10:
        severity = "medium"
        desc_extra = "A large subdomain footprint increases attack surface. Review each subdomain to confirm it is still needed and properly secured."
    else:
        severity = "info"
        desc_extra = "Review each subdomain to confirm it is still active and properly secured."

    # More subdomains → higher weight within the severity range
    sub_weight = min(1.0, count / 50)
    findings.append(
        Finding(
            id=_finding_id("crtsh_subdomains", domain, str(count)),
            finding_type="threat_exposure",
            severity=severity,
            severity_score=_severity_score(severity, sub_weight),
            title=f"{count} subdomain(s) found in Certificate Transparency logs for {domain}",
            description=(
                f"Certificate Transparency logs (crt.sh) reveal {count} subdomain(s) "
                f"associated with {domain}. {desc_extra}"
            ),
            evidence={
                "domain": domain,
                "subdomain_count": count,
                "subdomains": crt.subdomains[:20],
            },
            source="crtsh",
            affected_assets=crt.subdomains[:10],
        )
    )

    return findings


# ---------------------------------------------------------------------------
# HIBP findings
# ---------------------------------------------------------------------------


def _threat_from_hibp(domain: str, hibp: HibpResult) -> list[Finding]:  # noqa: F821
    findings: list[Finding] = []
    if hibp.skipped or hibp.error or hibp.breaches_found == 0:
        return findings

    severity = "critical" if hibp.breaches_found >= 5 else "high"
    breach_weight = min(1.0, hibp.breaches_found / 15)
    findings.append(
        Finding(
            id=_finding_id("hibp_breaches", domain, str(hibp.breaches_found)),
            finding_type="threat_exposure",
            severity=severity,
            severity_score=_severity_score(severity, breach_weight),
            title=f"{hibp.breaches_found} account breach(es) associated with {domain}",
            description=(
                f"Have I Been Pwned found {hibp.breaches_found} publicly-known data breach(es) "
                f"affecting accounts registered with {domain}. "
                "Compromised credentials are a leading cause of initial access in ransomware "
                "and BEC attacks. Require password resets and enforce MFA immediately."
            ),
            evidence={
                "domain": domain,
                "breaches_found": hibp.breaches_found,
                "breach_names": hibp.breach_names[:10],
            },
            source="hibp",
            affected_assets=[domain],
        )
    )

    return findings


# ---------------------------------------------------------------------------
# Security profile findings (Phase 3)
# ---------------------------------------------------------------------------

# Ordered by category; severity applied if control is "no" or "unsure"
_SECURITY_CONTROLS_META: list[tuple[str, str, str, str]] = [
    # (key, label, category, severity_if_missing)
    ("mfa_enabled", "MFA enabled for all users", "Identity & Access", "high"),
    ("password_policy", "Password policy enforced", "Identity & Access", "medium"),
    ("sso_in_use", "SSO in use", "Identity & Access", "low"),
    ("edr_deployed", "EDR/antivirus deployed on all endpoints", "Endpoint Protection", "high"),
    ("devices_encrypted", "Devices encrypted", "Endpoint Protection", "high"),
    ("auto_patching", "Auto-patching enabled", "Endpoint Protection", "medium"),
    ("email_filtering", "Email filtering / gateway in place", "Email Security", "high"),
    ("phishing_training", "Phishing awareness training conducted", "Email Security", "medium"),
    ("firewall_in_place", "Firewall in place", "Network", "high"),
    ("vpn_remote_access", "VPN for remote access", "Network", "medium"),
    ("network_segmentation", "Network segmentation implemented", "Network", "medium"),
    ("regular_backups", "Regular data backups performed", "Data Protection", "critical"),
    ("backup_testing", "Backup restoration tested", "Data Protection", "high"),
    ("data_classification", "Data classification policy exists", "Data Protection", "low"),
    ("ir_plan_documented", "Incident Response plan documented", "Incident Response", "high"),
    ("ir_plan_tested", "IR plan tested within 12 months", "Incident Response", "medium"),
]

_CONTROL_KEY_TO_META = {k: (label, cat, sev) for k, label, cat, sev in _SECURITY_CONTROLS_META}

# Compliance frameworks that match regulated industries and data types
_INDUSTRY_COMPLIANCE_MAP: dict[str, list[str]] = {
    "Healthcare": ["HIPAA"],
    "Finance & Insurance": ["PCI-DSS", "SOC 2"],
    "Government": ["CMMC", "NIST CSF"],
}

_DATA_TYPE_COMPLIANCE_MAP: dict[str, tuple[str, str]] = {
    # data_type_key: (compliance_framework, severity)
    "PHI (health records)": ("HIPAA", "critical"),
    "Payment card data": ("PCI-DSS", "high"),
}


def _analyze_security_profile(org: Organization) -> list[Finding]:  # noqa: F821
    """Generate findings from the org's security controls, compliance, and data type fields."""
    findings: list[Finding] = []

    # ── Security controls ────────────────────────────────────────────────────
    controls: dict[str, str] = org.security_controls or {}

    if not controls:
        findings.append(
            Finding(
                id=_finding_id("security_controls_empty"),
                finding_type="data_gap",
                severity="medium",
                severity_score=_severity_score("medium", 0.7),
                title="No security controls reported",
                description=(
                    "Your organization has not completed the security controls checklist. "
                    "Without this data, we cannot score your posture against the CIS IG1 baseline "
                    "or generate targeted recommendations. "
                    "Complete the checklist in Settings → Company Profile."
                ),
                evidence={},
                source="security_controls",
                affected_assets=[],
            )
        )
    else:
        for key, (label, category, severity) in _CONTROL_KEY_TO_META.items():
            value = controls.get(key, "unsure")
            if value in ("no", "unsure"):
                finding_severity = (
                    severity
                    if value == "no"
                    else ("medium" if severity in ("critical", "high") else "low")
                )
                # "no" is more severe than "unsure" within the same label range
                control_weight = 0.7 if value == "no" else 0.3
                findings.append(
                    Finding(
                        id=_finding_id("security_control", key, value),
                        finding_type="recommended_action",
                        severity=finding_severity,
                        severity_score=_severity_score(finding_severity, control_weight),
                        title=f"{category}: {label} — {'not in place' if value == 'no' else 'status unknown'}",
                        description=(
                            f"Security control '{label}' ({category}) is reported as "
                            f"{'not implemented' if value == 'no' else 'unknown/unsure'}. "
                            "This is a CIS IG1 essential hygiene control. "
                            "Implement or confirm its status to reduce your attack surface."
                        ),
                        evidence={"key": key, "value": value, "category": category},
                        source="security_controls",
                        affected_assets=[],
                    )
                )

    # ── Compliance gap: industry without expected framework ───────────────────
    frameworks: list[str] = org.compliance_frameworks or []
    industry = org.industry_label or ""

    expected_for_industry = _INDUSTRY_COMPLIANCE_MAP.get(industry, [])
    for fw in expected_for_industry:
        if fw not in frameworks:
            findings.append(
                Finding(
                    id=_finding_id("compliance_gap_industry", industry, fw),
                    finding_type="data_gap",
                    severity="high",
                    severity_score=_severity_score("high", 0.6),
                    title=f"{industry} organization not tracking {fw} compliance",
                    description=(
                        f"{fw} is a standard compliance requirement for {industry} organizations. "
                        "Not tracking it may indicate gaps in required controls and could expose "
                        "your organization to regulatory or legal risk."
                    ),
                    evidence={"industry": industry, "framework": fw},
                    source="compliance_frameworks",
                    affected_assets=[],
                )
            )

    # ── Compliance gap: data types without matching framework ─────────────────
    data_types: list[str] = org.data_types or []

    for data_type, (required_fw, severity) in _DATA_TYPE_COMPLIANCE_MAP.items():
        if data_type in data_types and required_fw not in frameworks:
            findings.append(
                Finding(
                    id=_finding_id("compliance_gap_data", data_type, required_fw),
                    finding_type="data_gap",
                    severity=severity,
                    severity_score=_severity_score(severity, 0.7),
                    title=f"Handles {data_type} but {required_fw} compliance is not tracked",
                    description=(
                        f"Your organization handles {data_type}, which requires {required_fw} compliance. "
                        f"Not having {required_fw} controls in place creates significant regulatory "
                        "and liability exposure. Add this framework to your compliance tracking immediately."
                    ),
                    evidence={"data_type": data_type, "required_framework": required_fw},
                    source="compliance_frameworks",
                    affected_assets=[],
                )
            )

    # ── Incident history signal ───────────────────────────────────────────────
    if org.incident_history and org.incident_history != "none":
        findings.append(
            Finding(
                id=_finding_id("incident_history", org.incident_history),
                finding_type="threat_exposure",
                severity="high",
                severity_score=_severity_score("high", 0.7),
                title=f"Prior cyber incident reported: {org.incident_history}",
                description=(
                    f"Your organization has experienced a {org.incident_history} incident in the past 24 months. "
                    "Organizations that have experienced a prior incident are statistically at higher risk "
                    "of repeat attacks. Review your defenses against this attack type specifically."
                ),
                evidence={"incident_type": org.incident_history},
                source="incident_history",
                affected_assets=[],
            )
        )

    return findings


# ---------------------------------------------------------------------------
# MITRE ATT&CK technique enrichment
# ---------------------------------------------------------------------------

# Curated mapping from IC3 attack type labels → relevant ATT&CK technique IDs + names.
# Source: MITRE ATT&CK Enterprise (v15), cross-referenced with FBI IC3 crime categories.
_IC3_TO_MITRE: dict[str, list[dict]] = {
    "Ransomware": [
        {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "Impact"},
        {"id": "T1490", "name": "Inhibit System Recovery", "tactic": "Impact"},
        {"id": "T1078", "name": "Valid Accounts (initial access)", "tactic": "Initial Access"},
        {"id": "T1566", "name": "Phishing (delivery)", "tactic": "Initial Access"},
        {"id": "T1047", "name": "Windows Management Instrumentation", "tactic": "Execution"},
    ],
    "Business Email Compromise": [
        {"id": "T1566", "name": "Phishing", "tactic": "Initial Access"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access"},
        {"id": "T1534", "name": "Internal Spearphishing", "tactic": "Lateral Movement"},
        {"id": "T1114", "name": "Email Collection", "tactic": "Collection"},
        {"id": "T1560", "name": "Archive Collected Data", "tactic": "Collection"},
    ],
    "Data Breach": [
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access"},
        {"id": "T1190", "name": "Exploit Public-Facing Application", "tactic": "Initial Access"},
        {"id": "T1005", "name": "Data from Local System", "tactic": "Collection"},
        {"id": "T1041", "name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration"},
        {"id": "T1048", "name": "Exfiltration Over Alternative Protocol", "tactic": "Exfiltration"},
    ],
    "Phishing": [
        {"id": "T1566.001", "name": "Spearphishing Attachment", "tactic": "Initial Access"},
        {"id": "T1566.002", "name": "Spearphishing Link", "tactic": "Initial Access"},
        {"id": "T1056", "name": "Input Capture (credential theft)", "tactic": "Collection"},
        {"id": "T1539", "name": "Steal Web Session Cookie", "tactic": "Credential Access"},
    ],
    "Investment Fraud": [
        {"id": "T1566", "name": "Phishing", "tactic": "Initial Access"},
        {"id": "T1598", "name": "Phishing for Information", "tactic": "Reconnaissance"},
    ],
    "Tech Support Fraud": [
        {"id": "T1566", "name": "Phishing", "tactic": "Initial Access"},
        {"id": "T1219", "name": "Remote Access Software", "tactic": "Command and Control"},
    ],
    "Identity Theft": [
        {"id": "T1589", "name": "Gather Victim Identity Information", "tactic": "Reconnaissance"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access"},
        {"id": "T1110", "name": "Brute Force", "tactic": "Credential Access"},
    ],
    "Corporate Data Theft": [
        {"id": "T1005", "name": "Data from Local System", "tactic": "Collection"},
        {"id": "T1213", "name": "Data from Information Repositories", "tactic": "Collection"},
        {"id": "T1048", "name": "Exfiltration Over Alternative Protocol", "tactic": "Exfiltration"},
    ],
    "Government Impersonation": [
        {"id": "T1566", "name": "Phishing", "tactic": "Initial Access"},
        {"id": "T1598", "name": "Phishing for Information", "tactic": "Reconnaissance"},
    ],
    "Real Estate Fraud": [
        {"id": "T1566", "name": "Phishing", "tactic": "Initial Access"},
        {"id": "T1114", "name": "Email Collection", "tactic": "Collection"},
    ],
    "Supply Chain Compromise": [
        {"id": "T1195", "name": "Supply Chain Compromise", "tactic": "Initial Access"},
        {"id": "T1072", "name": "Software Deployment Tools", "tactic": "Execution"},
        {"id": "T1199", "name": "Trusted Relationship", "tactic": "Initial Access"},
    ],
    "Malware": [
        {"id": "T1059", "name": "Command and Scripting Interpreter", "tactic": "Execution"},
        {"id": "T1055", "name": "Process Injection", "tactic": "Defense Evasion"},
        {"id": "T1071", "name": "Application Layer Protocol (C2)", "tactic": "Command and Control"},
    ],
}

# ATT&CK mitigations that map to existing security control keys
_MITRE_MITIGATIONS: dict[str, str] = {
    "T1566": "M1049 (Antivirus/Antimalware), M1031 (Network Intrusion Prevention), M1017 (User Training)",
    "T1566.001": "M1049 (Antivirus), M1017 (Phishing Awareness Training)",
    "T1566.002": "M1054 (Software Configuration), M1021 (Restrict Web-Based Content)",
    "T1078": "M1032 (Multi-factor Authentication), M1027 (Password Policies)",
    "T1190": "M1016 (Vulnerability Scanning), M1048 (Application Isolation and Sandboxing)",
    "T1486": "M1040 (Behavior Prevention on Endpoint), M1053 (Data Backup)",
    "T1490": "M1053 (Data Backup), M1028 (Operating System Configuration)",
    "T1110": "M1032 (Multi-factor Authentication), M1036 (Account Use Policies)",
    "T1114": "M1032 (Multi-factor Authentication), M1041 (Encrypt Sensitive Information)",
}


def _enrich_finding_with_mitre(finding: Finding, attack_type: str) -> None:
    """Attach MITRE ATT&CK technique references to an existing threat_exposure finding."""
    if "mitre_techniques" in finding.evidence:
        return  # already enriched — skip to preserve idempotency
    techniques = _IC3_TO_MITRE.get(attack_type, [])
    if not techniques:
        return
    finding.evidence["mitre_techniques"] = techniques
    top_mitigations = [
        _MITRE_MITIGATIONS[t["id"]] for t in techniques[:3] if t["id"] in _MITRE_MITIGATIONS
    ]
    if top_mitigations:
        finding.evidence["mitre_mitigations"] = top_mitigations


# ---------------------------------------------------------------------------
# Technology fingerprint findings
# ---------------------------------------------------------------------------

# Risky tech patterns: if detected, emit a recommended_action finding
_RISKY_TECH_PATTERNS: list[dict] = [
    {
        "match_names": ["WordPress", "Drupal", "Joomla"],
        "severity": "medium",
        "title": "CMS detected — keep it patched",
        "description": (
            "{name} is detected on your domain. CMSes are a top target for exploitation; "
            "outdated versions account for a significant share of web compromises. "
            "Ensure automatic updates are enabled and plugins/themes are kept current."
        ),
    },
    {
        "match_names": ["PHP"],
        "severity": "low",
        "title": "PHP server-side language detected",
        "description": (
            "PHP is detected on {domain}. PHP applications are frequently targeted for "
            "injection and deserialization vulnerabilities. Confirm the PHP version is "
            "supported and patched, and review OWASP Top 10 hardening for PHP."
        ),
    },
    {
        "match_names": ["Microsoft IIS", "ASP.NET"],
        "severity": "low",
        "title": "Microsoft IIS/ASP.NET detected",
        "description": (
            "Microsoft IIS and/or ASP.NET is detected on {domain}. Ensure the server "
            "is running a supported version and all Windows/IIS security patches are applied. "
            "Review IIS hardening guides and disable unused HTTP methods."
        ),
    },
]

# Category-level tech inventory signals (info-only, no risk finding)
_INTERESTING_CATEGORIES = {
    "CMS",
    "E-commerce",
    "Web Framework",
    "Web Server",
    "Programming Language",
}


def _tech_fingerprint_findings(domain: str, tech: TechFingerprintResult) -> list[Finding]:
    """Generate findings from detected technologies."""
    findings: list[Finding] = []
    if tech.error or not tech.detected:
        return findings

    detected_names = {d["name"] for d in tech.detected}

    # Inventory finding — list what was detected (info severity)
    categories_seen = {
        cat
        for d in tech.detected
        for cat in d.get("categories", [])
        if cat in _INTERESTING_CATEGORIES
    }
    if detected_names:
        findings.append(
            Finding(
                id=_finding_id(
                    "tech_fingerprint_inventory", domain, ",".join(sorted(detected_names))
                ),
                finding_type="threat_exposure",
                severity="info",
                severity_score=_severity_score("info", 0.5),
                title=f"Technology stack detected on {domain}",
                description=(
                    f"Passive fingerprinting detected the following technologies on {domain}: "
                    f"{', '.join(sorted(detected_names))}. "
                    "This information is also visible to attackers during reconnaissance. "
                    "Review each component for known vulnerabilities and consider suppressing "
                    "server/framework version headers."
                ),
                evidence={
                    "domain": domain,
                    "detected_technologies": tech.detected,
                    "categories": sorted(categories_seen),
                },
                source="tech_fingerprint",
                affected_assets=[domain],
            )
        )

    # Risk-based findings for known-risky tech patterns
    for pattern in _RISKY_TECH_PATTERNS:
        matches = [n for n in pattern["match_names"] if n in detected_names]
        if matches:
            matched_name = matches[0]
            findings.append(
                Finding(
                    id=_finding_id("tech_risk", domain, matched_name),
                    finding_type="recommended_action",
                    severity=pattern["severity"],
                    severity_score=_severity_score(pattern["severity"], 0.5),
                    title=f"{pattern['title'].format(name=matched_name)}",
                    description=pattern["description"].format(name=matched_name, domain=domain),
                    evidence={"domain": domain, "detected": matched_name},
                    source="tech_fingerprint",
                    affected_assets=[domain],
                )
            )
            break  # one risk finding per domain, highest priority match first

    return findings


# ---------------------------------------------------------------------------
# Shodan host findings
# ---------------------------------------------------------------------------

# Ports that are high-risk when exposed to the internet
_HIGH_RISK_PORTS: dict[int, tuple[str, str]] = {
    21: ("FTP", "high"),
    23: ("Telnet", "critical"),
    25: ("SMTP (direct)", "medium"),
    445: ("SMB", "critical"),
    1433: ("MS SQL Server", "high"),
    1521: ("Oracle DB", "high"),
    3306: ("MySQL", "high"),
    3389: ("RDP (Remote Desktop)", "critical"),
    4444: ("Metasploit default", "critical"),
    5432: ("PostgreSQL", "high"),
    5900: ("VNC", "high"),
    6379: ("Redis (no auth)", "high"),
    8080: ("HTTP alternate (unencrypted)", "low"),
    8443: ("HTTPS alternate", "low"),
    27017: ("MongoDB", "high"),
}


def _shodan_findings(domain: str, shodan: ShodanHostResult) -> list[Finding]:
    """Generate findings from Shodan host data."""
    findings: list[Finding] = []
    if shodan.skipped or shodan.error or not shodan.ip:
        return findings

    # Risky open ports
    risky = [
        (port, *_HIGH_RISK_PORTS[port]) for port in shodan.open_ports if port in _HIGH_RISK_PORTS
    ]

    for port, service_name, severity in risky:
        findings.append(
            Finding(
                id=_finding_id("shodan_port", domain, str(port)),
                finding_type="threat_exposure",
                severity=severity,
                severity_score=_severity_score(severity, 0.7),
                title=f"{service_name} (port {port}) is internet-accessible on {domain}",
                description=(
                    f"Shodan reports that port {port} ({service_name}) is open and accessible from the internet "
                    f"on {shodan.ip} ({domain}). "
                    "Exposing this service publicly is a significant attack vector. "
                    "Restrict access via firewall rules to known IP ranges, or disable if not required."
                ),
                evidence={"domain": domain, "ip": shodan.ip, "port": port, "service": service_name},
                source="shodan",
                affected_assets=[domain],
            )
        )

    # CVEs detected by Shodan
    if shodan.vulns:
        count = len(shodan.vulns)
        severity = "critical" if count >= 5 else "high"
        vuln_weight = min(1.0, count / 10)
        findings.append(
            Finding(
                id=_finding_id("shodan_vulns", domain, str(count)),
                finding_type="vendor_exposure",
                severity=severity,
                severity_score=_severity_score(severity, vuln_weight),
                title=f"Shodan detected {count} CVE(s) on internet-facing infrastructure at {domain}",
                description=(
                    f"Shodan's passive scanning found {count} CVE(s) on the internet-facing host "
                    f"at {shodan.ip} ({domain}): {', '.join(shodan.vulns[:5])}"
                    f"{'...' if count > 5 else ''}. "
                    "These vulnerabilities are visible to any attacker scanning the internet. "
                    "Apply patches immediately and consider blocking unnecessary ports at the firewall."
                ),
                evidence={
                    "domain": domain,
                    "ip": shodan.ip,
                    "cves": shodan.vulns,
                    "isp": shodan.isp,
                },
                source="shodan",
                affected_assets=[domain],
            )
        )

    # Internet exposure inventory (info)
    if shodan.open_ports and not risky and not shodan.vulns:
        findings.append(
            Finding(
                id=_finding_id("shodan_exposure", domain),
                finding_type="threat_exposure",
                severity="info",
                severity_score=_severity_score("info", 0.5),
                title=f"Internet-facing services inventoried on {domain}",
                description=(
                    f"Shodan reports {len(shodan.open_ports)} open port(s) on {shodan.ip} ({domain}): "
                    f"{', '.join(str(p) for p in shodan.open_ports[:10])}. "
                    "No high-risk ports were detected. Review periodically to confirm "
                    "only intentionally public services are exposed."
                ),
                evidence={"domain": domain, "ip": shodan.ip, "open_ports": shodan.open_ports},
                source="shodan",
                affected_assets=[domain],
            )
        )

    return findings


# ---------------------------------------------------------------------------
# AlienVault OTX threat intel findings
# ---------------------------------------------------------------------------


def _otx_findings(domain: str, otx: OtxResult) -> list[Finding]:
    """Generate findings from AlienVault OTX threat pulse data."""
    findings: list[Finding] = []
    if otx.skipped or otx.error:
        return findings

    if otx.pulse_count == 0:
        return findings

    severity = "critical" if otx.pulse_count >= 10 else "high" if otx.pulse_count >= 3 else "medium"
    # Scale score by pulse count within the severity range
    pulse_weight = min(1.0, otx.pulse_count / 20)

    malware_str = ""
    if otx.malware_families:
        malware_str = f" Associated malware families: {', '.join(otx.malware_families[:5])}."

    findings.append(
        Finding(
            id=_finding_id("otx_pulses", domain, str(otx.pulse_count)),
            finding_type="threat_exposure",
            severity=severity,
            severity_score=_severity_score(severity, pulse_weight),
            title=f"{domain} appears in {otx.pulse_count} threat intelligence pulse(s)",
            description=(
                f"AlienVault OTX — a crowd-sourced threat intelligence feed — has flagged "
                f"{domain} in {otx.pulse_count} active threat pulse(s).{malware_str} "
                "This may indicate your domain has been observed in phishing campaigns, "
                "malware distribution, or other malicious activity. "
                "Review OTX pulse details and investigate any unauthorized use of your domain."
            ),
            evidence={
                "domain": domain,
                "pulse_count": otx.pulse_count,
                "malware_families": otx.malware_families,
                "reputation_score": otx.reputation_score,
            },
            source="otx",
            affected_assets=[domain],
        )
    )

    return findings


# ---------------------------------------------------------------------------
# Recommended actions synthesis
# ---------------------------------------------------------------------------


def _synthesize_recommendations(all_findings: list[Finding]) -> list[Finding]:
    """Generate high-level recommended_action findings from existing findings."""
    recs: list[Finding] = []

    # Collect existing rec IDs and keywords to avoid semantic overlap
    existing_rec_ids = {f.id for f in all_findings if f.finding_type == "recommended_action"}
    existing_rec_titles = {
        f.title.lower() for f in all_findings if f.finding_type == "recommended_action"
    }

    def _is_duplicate(rec: Finding) -> bool:
        if rec.id in existing_rec_ids:
            return True
        # Check for keyword overlap with existing rec titles
        rec_words = set(rec.title.lower().split())
        for title in existing_rec_titles:
            title_words = set(title.split())
            overlap = rec_words & title_words - {
                "to",
                "the",
                "a",
                "and",
                "or",
                "for",
                "your",
                "is",
                "in",
                "on",
            }
            if len(overlap) >= 3:
                return True
        return False

    # DNS email security recommendation
    dns_findings = [
        f for f in all_findings if f.source == "dns_checks" and f.finding_type == "threat_exposure"
    ]
    if dns_findings:
        affected = list({a for f in dns_findings for a in f.affected_assets})
        recs.append(
            Finding(
                id=_finding_id("rec_email_security"),
                finding_type="recommended_action",
                severity="high",
                severity_score=_severity_score("high", 0.6),
                title="Configure email security records (SPF/DMARC) to prevent spoofing",
                description=(
                    f"Your domain has {len(dns_findings)} email security gap(s). "
                    "Add SPF to authorize legitimate mail servers, and set DMARC to "
                    "'quarantine' or 'reject' to stop spoofed emails. "
                    "This addresses a significant phishing and BEC risk at zero cost."
                ),
                evidence={"dns_finding_count": len(dns_findings)},
                source="findings_synthesis",
                affected_assets=affected,
            )
        )

    # Vendor patching recommendation
    critical_vendor = next(
        (f for f in all_findings if f.source == "kev_vendor_match" and f.severity == "critical"),
        None,
    )
    if critical_vendor:
        recs.append(
            Finding(
                id=_finding_id("rec_vendor_patching"),
                finding_type="recommended_action",
                severity="critical",
                severity_score=_severity_score("critical", 0.8),
                title="Audit and patch critical CVEs in your technology stack immediately",
                description=(
                    "Your vendor stack has critical known-exploited vulnerabilities. "
                    "Review the Vendor Alerts tab for the full list. "
                    "Prioritize CVEs with upcoming CISA deadlines and those rated Critical. "
                    "Apply vendor patches, enable auto-update where possible, or isolate "
                    "affected systems until patched."
                ),
                evidence={},
                source="findings_synthesis",
                affected_assets=[],
            )
        )

    # Profile completion recommendation
    data_gap_required = [
        f for f in all_findings if f.finding_type == "data_gap" and f.evidence.get("required")
    ]
    if data_gap_required:
        recs.append(
            Finding(
                id=_finding_id("rec_complete_profile"),
                finding_type="recommended_action",
                severity="medium",
                severity_score=_severity_score("medium", 0.5),
                title=f"Complete {len(data_gap_required)} required profile field(s) to improve assessment accuracy",
                description=(
                    "Several required fields in your organization profile are empty. "
                    "Completing them enables sector-specific threat analysis, vendor CVE matching, "
                    "and more accurate loss projections. "
                    "Go to Settings → Company Profile to update them."
                ),
                evidence={"missing_required_count": len(data_gap_required)},
                source="findings_synthesis",
                affected_assets=[],
            )
        )

    return [r for r in recs if not _is_duplicate(r)]


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def _build_summary(findings: list[Finding]) -> FindingsSummary:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for f in findings:
        by_type[f.finding_type] = by_type.get(f.finding_type, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return FindingsSummary(
        total=len(findings),
        by_type=by_type,
        by_severity=by_severity,
    )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class FindingsEngine:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(self, org: Organization, *, persist: bool = False) -> FindingsReport:  # noqa: C901
        """Build a findings report for the given organization."""
        data_sources_used: list[str] = []

        # ── Fetch domains ─────────────────────────────────────────────────────
        domain_result = await self._db.execute(
            select(OrgDomain.domain_name).where(OrgDomain.org_id == org.id)
        )
        domains = [row[0] for row in domain_result.all()]
        primary_domain = org.primary_domain or (domains[0] if domains else None)

        # ── Gather signal sources concurrently ───────────────────────────────
        vendor_alert_task = VendorAlertService(self._db).get_alerts(org.id, page=1, page_size=100)
        readiness_task = evaluate_readiness(org, self._db)

        vendor_alerts_resp, readiness_resp = await asyncio.gather(
            vendor_alert_task,
            readiness_task,
        )

        # ── Risk score (synchronous) ─────────────────────────────────────────
        calculate_smb_risk_score(org.industry_label, org.employee_range)

        # ── IC3 sector mapping ───────────────────────────────────────────────
        ic3_sector: str | None = None
        if org.industry_label:
            try:
                ic3_sector = INDUSTRY_TO_IC3_SECTOR.get(IndustryLabel(org.industry_label))
            except ValueError:
                ic3_sector = None

        # ── Domain checks (Tier 1 + Tier 2) ─────────────────────────────────
        dns_result = http_result = ssl_result = None
        tech_result = None
        crt_result = hibp_result = shodan_result = otx_result = None

        if primary_domain:
            hibp_api_key = getattr(settings, "HIBP_API_KEY", "") or None
            shodan_api_key = getattr(settings, "SHODAN_API_KEY", "") or None
            otx_api_key = getattr(settings, "OTX_API_KEY", "") or None

            tier1_task = run_tier1_checks(primary_domain)
            tier2_task = run_tier2_checks(primary_domain, hibp_api_key, shodan_api_key, otx_api_key)

            (
                (dns_result, http_result, ssl_result, tech_result),
                (crt_result, hibp_result, shodan_result, otx_result),
            ) = await asyncio.gather(tier1_task, tier2_task)

            if not dns_result.error:
                data_sources_used.append("dns_checks")
            if http_result.reachable:
                data_sources_used.append("http_header_checks")
            if ssl_result.reachable:
                data_sources_used.append("ssl_checks")
            if tech_result and not tech_result.error:
                data_sources_used.append("tech_fingerprint")
            if crt_result and not crt_result.error:
                data_sources_used.append("crtsh")
            if hibp_result and not hibp_result.skipped and not hibp_result.error:
                data_sources_used.append("hibp")
            if shodan_result and not shodan_result.skipped and not shodan_result.error:
                data_sources_used.append("shodan")
            if otx_result and not otx_result.skipped and not otx_result.error:
                data_sources_used.append("otx")

        # ── Always-active sources ────────────────────────────────────────────
        data_sources_used.extend(
            ["ic3_sector_weights", "kev_vendor_match", "assessment_readiness", "mitre_attack"]
        )

        # ── Generate findings ────────────────────────────────────────────────
        findings: list[Finding] = []

        # Threat exposure — sector + domain
        sector_findings = _threat_exposure_from_sector(ic3_sector, org.industry_label)
        findings.extend(sector_findings)
        if primary_domain and dns_result:
            findings.extend(_threat_exposure_from_dns(primary_domain, dns_result))
        if primary_domain and ssl_result:
            findings.extend(_threat_exposure_from_ssl(primary_domain, ssl_result))
        if primary_domain and crt_result:
            findings.extend(_recommended_from_crtsh(primary_domain, crt_result))
        if primary_domain and hibp_result:
            findings.extend(_threat_from_hibp(primary_domain, hibp_result))

        # Tech fingerprint findings
        if primary_domain and tech_result:
            findings.extend(_tech_fingerprint_findings(primary_domain, tech_result))

        # Shodan host intelligence
        if primary_domain and shodan_result:
            findings.extend(_shodan_findings(primary_domain, shodan_result))

        # AlienVault OTX threat intel
        if primary_domain and otx_result:
            findings.extend(_otx_findings(primary_domain, otx_result))

        # Enrich sector threat_exposure findings with MITRE ATT&CK techniques
        for finding in sector_findings:
            if finding.finding_type == "threat_exposure":
                attack_type = finding.evidence.get("attack_type", "")
                _enrich_finding_with_mitre(finding, attack_type)

        # Vendor exposure
        vendor_dict = {
            "total_matched": vendor_alerts_resp.total_matched,
            "severity_breakdown": {
                "critical": vendor_alerts_resp.severity_breakdown.critical,
                "high": vendor_alerts_resp.severity_breakdown.high,
                "medium": vendor_alerts_resp.severity_breakdown.medium,
                "low": vendor_alerts_resp.severity_breakdown.low,
            },
            "unmatched_vendors": vendor_alerts_resp.unmatched_vendors,
            "reason": vendor_alerts_resp.reason,
            "items": [
                {
                    "vendor_name": a.vendor_name,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "severity_label": a.severity_label,
                    "match_confidence": a.match_confidence,
                }
                for a in vendor_alerts_resp.items
            ],
        }
        findings.extend(_vendor_exposure_findings(vendor_dict))

        # Data gaps
        readiness_dict = {
            "tier": readiness_resp.tier,
            "items": [
                {
                    "key": item.key,
                    "label": item.label,
                    "complete": item.complete,
                    "required": item.required,
                }
                for item in readiness_resp.items
            ],
        }
        findings.extend(_data_gap_findings(readiness_dict))

        # HTTP header recommendations
        if primary_domain and http_result:
            findings.extend(_recommended_from_http_headers(primary_domain, http_result))

        # Security profile (controls, compliance, data types, incident history)
        findings.extend(_analyze_security_profile(org))

        # Synthesized recommendations
        findings.extend(_synthesize_recommendations(findings))

        # ── Sort by severity (use numeric score for finer ordering) ─────────
        findings.sort(key=lambda f: -(f.severity_score or _severity_score(f.severity, 0.5)))

        sorted_sources = sorted(set(data_sources_used))
        disclaimer_block = get_disclaimer(
            DisclaimerContext.FINDINGS,
            tier=readiness_resp.tier,
            data_sources=sorted_sources,
        )

        report = FindingsReport(
            org_id=org.id,
            findings=findings,
            summary=_build_summary(findings),
            generated_at=datetime.now(UTC).isoformat(),
            data_sources_used=sorted_sources,
            assessment_tier=readiness_resp.tier,
            disclaimer_block=disclaimer_block,
        )

        if persist:
            await self._persist_snapshot(report)

        return report

    async def _persist_snapshot(self, report: FindingsReport) -> None:
        """Save a findings snapshot to the database."""
        from app.db.findings_snapshot import FindingsSnapshot

        snapshot = FindingsSnapshot(
            org_id=report.org_id,
            generated_at=datetime.fromisoformat(report.generated_at),
            findings=[f.model_dump() for f in report.findings],
            summary=report.summary.model_dump(),
            assessment_tier=report.assessment_tier,
            data_sources_used=report.data_sources_used,
        )
        self._db.add(snapshot)
        await self._db.commit()
