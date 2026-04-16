"""Centralized disclaimer registry — single source of truth for all assessment-facing text."""

from __future__ import annotations

from enum import Enum

from app.schemas.disclaimer import DisclaimerBlock

# ── Shared constants ──────────────────────────────────────────────────────────

_BASE_DISCLAIMER = (
    "This information is generated for educational and informational purposes only "
    "and does not constitute professional cybersecurity advice. Consult a qualified "
    "cybersecurity professional for organization-specific assessments."
)

_TRANSPARENCY_NOTE = (
    "Generated from available company-provided information and public threat "
    "intelligence data."
)


# ── Context enum ──────────────────────────────────────────────────────────────


class DisclaimerContext(str, Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    AI_SUMMARY = "ai_summary"
    FINDINGS = "findings"
    SMB_ADVISOR = "smb_advisor"
    LOSS_PROJECTION = "loss_projection"
    RISK_SCORE = "risk_score"


# ── Context-specific primary text ─────────────────────────────────────────────

_PRIMARY_TEXT: dict[DisclaimerContext, str] = {
    DisclaimerContext.EXECUTIVE_SUMMARY: (
        "This summary is generated from aggregate public threat-intelligence data and does not "
        "reflect your organization's specific security posture, installed software, or network "
        "configuration. Do not use this score as the sole basis for security decisions."
    ),
    DisclaimerContext.AI_SUMMARY: (
        "This summary is generated from automated threat intelligence data and is intended "
        "for informational purposes only. It does not constitute professional security advice."
    ),
    DisclaimerContext.FINDINGS: (
        "Findings are derived from public vulnerability databases, domain reconnaissance, "
        "and company-provided profile data. Results may not capture all threats and should "
        "be validated by a qualified security professional."
    ),
    DisclaimerContext.SMB_ADVISOR: (
        "Data sourced from the FBI Internet Crime Complaint Center (IC3) and the National "
        "Vulnerability Database (NVD). Figures represent aggregated complaint data and may "
        "not reflect all incidents — the majority of cybercrimes go unreported."
    ),
    DisclaimerContext.LOSS_PROJECTION: (
        "Loss projections are statistical estimates based on historical IC3 data and industry "
        "benchmarks. Actual losses may vary significantly based on organizational controls and "
        "incident response capabilities."
    ),
    DisclaimerContext.RISK_SCORE: (
        "Risk scores combine multiple public threat-intelligence sources and are intended as "
        "a relative indicator, not an absolute measure of organizational risk."
    ),
}


# ── Tier → confidence message ─────────────────────────────────────────────────

_CONFIDENCE_MESSAGES: dict[str, str] = {
    "incomplete": "Very limited data — complete your organization profile to enable assessment.",
    "basic": "Baseline confidence — core profile fields provided. Add vendors and domains to improve accuracy.",
    "enhanced": "Good confidence — vendor and domain intelligence included in analysis.",
    "comprehensive": "Highest confidence — full organizational context enables the most accurate analysis.",
    # Legacy tier names (backward compat)
    "minimal": "Baseline confidence — core profile fields provided. Add vendors and domains to improve accuracy.",
    "good": "Good confidence — vendor and domain intelligence included in analysis.",
}


def get_confidence_message(tier: str) -> str:
    """Map an intake tier to a human-friendly confidence description."""
    return _CONFIDENCE_MESSAGES.get(tier.lower(), _CONFIDENCE_MESSAGES["basic"])


def get_disclaimer(
    context: DisclaimerContext,
    *,
    tier: str = "basic",
    data_sources: list[str] | None = None,
) -> DisclaimerBlock:
    """Build a contextual disclaimer block.

    Parameters
    ----------
    context:
        Which view/feature this disclaimer is for.
    tier:
        Current assessment intake tier (drives confidence text).
    data_sources:
        List of data source keys used in the analysis (e.g. ``["ic3", "nvd", "kev"]``).
    """
    primary = _PRIMARY_TEXT.get(context, _BASE_DISCLAIMER)
    confidence = get_confidence_message(tier)

    if data_sources:
        source_labels = _format_sources(data_sources)
        attribution = f"Data sources: {source_labels}"
    else:
        attribution = "Data sources: public threat intelligence databases"

    return DisclaimerBlock(
        primary_text=primary,
        confidence_text=confidence,
        data_source_attribution=attribution,
        transparency_note=_TRANSPARENCY_NOTE,
    )


# ── Source label mapping ──────────────────────────────────────────────────────

_SOURCE_LABELS: dict[str, str] = {
    "ic3_sector_weights": "FBI IC3",
    "kev_vendor_match": "CISA KEV",
    "assessment_readiness": "Profile Assessment",
    "mitre_attack": "MITRE ATT&CK",
    "dns_checks": "DNS",
    "http_header_checks": "HTTP Headers",
    "ssl_checks": "SSL/TLS",
    "tech_fingerprint": "Technology Fingerprint",
    "crtsh": "Certificate Transparency",
    "hibp": "Have I Been Pwned",
    "shodan": "Shodan",
    "otx": "AlienVault OTX",
}


def _format_sources(keys: list[str]) -> str:
    """Convert internal source keys to human-readable labels, deduped."""
    labels = []
    seen: set[str] = set()
    for key in keys:
        label = _SOURCE_LABELS.get(key, key.replace("_", " ").title())
        if label not in seen:
            labels.append(label)
            seen.add(label)
    return ", ".join(labels)
