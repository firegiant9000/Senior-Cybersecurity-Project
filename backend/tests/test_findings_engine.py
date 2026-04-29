"""Tests for the Findings Engine and domain checks.

Covers:
  - Threat exposure findings from sector weights
  - Threat exposure findings from DNS (SPF/DMARC)
  - Threat exposure findings from SSL
  - Vendor exposure findings from KEV data
  - Data gap findings from readiness items
  - HTTP header recommended_action findings
  - Recommendation synthesis
  - crt.sh and HIBP findings
  - Tech fingerprint findings (Phase 6)
  - MITRE ATT&CK enrichment (Phase 6)
  - Shodan host findings (Phase 6)
  - AlienVault OTX findings (Phase 6)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.domain_checks import (
    CrtShResult,
    DnsCheckResult,
    HibpResult,
    HttpHeaderResult,
    OtxResult,
    ShodanHostResult,
    SslCheckResult,
    TechFingerprintResult,
)
from app.services.findings_engine import (
    FindingsEngine,
    _analyze_security_profile,
    _data_gap_findings,
    _enrich_finding_with_mitre,
    _otx_findings,
    _recommended_from_crtsh,
    _recommended_from_http_headers,
    _shodan_findings,
    _synthesize_recommendations,
    _tech_fingerprint_findings,
    _threat_exposure_from_dns,
    _threat_exposure_from_sector,
    _threat_exposure_from_ssl,
    _threat_from_hibp,
    _vendor_exposure_findings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _readiness_items(
    *,
    missing_keys: list[str] | None = None,
    required_keys: list[str] | None = None,
):
    all_keys = ["org_name", "industry", "state", "employee_range", "vendors", "domains"]
    required_keys = required_keys or all_keys
    missing_keys = missing_keys or []
    return [
        {
            "key": k,
            "label": k.replace("_", " ").title(),
            "complete": k not in missing_keys,
            "required": k in required_keys,
        }
        for k in all_keys
    ]


def _vendor_dict(
    total_matched=0,
    critical=0,
    high=0,
    medium=0,
    low=0,
    unmatched=None,
    reason=None,
    items=None,
):
    return {
        "total_matched": total_matched,
        "severity_breakdown": {"critical": critical, "high": high, "medium": medium, "low": low},
        "unmatched_vendors": unmatched or [],
        "reason": reason,
        "items": items or [],
    }


# ---------------------------------------------------------------------------
# Threat exposure — sector
# ---------------------------------------------------------------------------


class TestThreatExposureSector:
    def test_no_sector_returns_empty(self):
        assert _threat_exposure_from_sector(None, None) == []

    def test_known_sector_returns_findings(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        assert len(findings) > 0
        types = {f.finding_type for f in findings}
        assert "threat_exposure" in types

    def test_high_weight_sector_is_high_severity(self):
        # Healthcare has ransomware weight 0.22 which is >= 0.20
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        ransomware = next((f for f in findings if "Ransomware" in f.title), None)
        assert ransomware is not None
        assert ransomware.severity == "high"

    def test_source_is_ic3_sector_weights(self):
        findings = _threat_exposure_from_sector("Finance", "Finance & Insurance")
        assert all(f.source == "ic3_sector_weights" for f in findings)

    def test_unknown_sector_returns_empty(self):
        findings = _threat_exposure_from_sector("NotARealSector", "Fake Industry")
        assert findings == []

    def test_finding_id_is_deterministic(self):
        f1 = _threat_exposure_from_sector("Healthcare", "Healthcare")
        f2 = _threat_exposure_from_sector("Healthcare", "Healthcare")
        assert [f.id for f in f1] == [f.id for f in f2]


# ---------------------------------------------------------------------------
# Threat exposure — DNS
# ---------------------------------------------------------------------------


class TestThreatExposureDns:
    def test_no_spf_produces_finding(self):
        dns = DnsCheckResult(
            domain="example.com", spf_found=False, dmarc_found=True, dmarc_policy="reject"
        )
        findings = _threat_exposure_from_dns("example.com", dns)
        assert any("SPF" in f.title for f in findings)

    def test_no_dmarc_produces_finding(self):
        dns = DnsCheckResult(domain="example.com", spf_found=True, dmarc_found=False)
        findings = _threat_exposure_from_dns("example.com", dns)
        assert any("DMARC" in f.title for f in findings)

    def test_dmarc_policy_none_produces_medium(self):
        dns = DnsCheckResult(
            domain="example.com", spf_found=True, dmarc_found=True, dmarc_policy="none"
        )
        findings = _threat_exposure_from_dns("example.com", dns)
        dmarc_finding = next((f for f in findings if "DMARC" in f.title), None)
        assert dmarc_finding is not None
        assert dmarc_finding.severity == "medium"

    def test_dmarc_reject_no_finding(self):
        dns = DnsCheckResult(
            domain="example.com", spf_found=True, dmarc_found=True, dmarc_policy="reject"
        )
        findings = _threat_exposure_from_dns("example.com", dns)
        assert not any("DMARC" in f.title for f in findings)

    def test_dns_error_returns_empty(self):
        dns = DnsCheckResult(domain="example.com", error="timeout")
        assert _threat_exposure_from_dns("example.com", dns) == []

    def test_no_spf_finding_is_high_severity(self):
        dns = DnsCheckResult(
            domain="example.com", spf_found=False, dmarc_found=True, dmarc_policy="reject"
        )
        findings = _threat_exposure_from_dns("example.com", dns)
        spf_finding = next((f for f in findings if "SPF" in f.title), None)
        assert spf_finding is not None
        assert spf_finding.severity == "high"

    def test_all_records_present_no_findings(self):
        dns = DnsCheckResult(
            domain="example.com",
            spf_found=True,
            dmarc_found=True,
            dmarc_policy="reject",
            dkim_selector_found=True,
        )
        assert _threat_exposure_from_dns("example.com", dns) == []


# ---------------------------------------------------------------------------
# Threat exposure — SSL
# ---------------------------------------------------------------------------


class TestThreatExposureSsl:
    def test_self_signed_produces_high(self):
        ssl_r = SslCheckResult(domain="example.com", reachable=True, self_signed=True)
        findings = _threat_exposure_from_ssl("example.com", ssl_r)
        assert any(
            f.severity == "high" and f.evidence.get("self_signed") is True
            for f in findings
        )

    def test_cert_expiring_7_days_is_critical(self):
        from datetime import UTC, datetime, timedelta

        ssl_r = SslCheckResult(
            domain="example.com",
            reachable=True,
            self_signed=False,
            days_until_expiry=5,
            expiry=datetime.now(UTC) + timedelta(days=5),
        )
        findings = _threat_exposure_from_ssl("example.com", ssl_r)
        assert any(f.severity == "critical" for f in findings)

    def test_cert_expiring_20_days_is_high(self):
        from datetime import UTC, datetime, timedelta

        ssl_r = SslCheckResult(
            domain="example.com",
            reachable=True,
            self_signed=False,
            days_until_expiry=20,
            expiry=datetime.now(UTC) + timedelta(days=20),
        )
        findings = _threat_exposure_from_ssl("example.com", ssl_r)
        assert any(f.severity == "high" for f in findings)

    def test_cert_healthy_no_findings(self):
        from datetime import UTC, datetime, timedelta

        ssl_r = SslCheckResult(
            domain="example.com",
            reachable=True,
            self_signed=False,
            days_until_expiry=365,
            expiry=datetime.now(UTC) + timedelta(days=365),
        )
        assert _threat_exposure_from_ssl("example.com", ssl_r) == []

    def test_unreachable_no_findings(self):
        ssl_r = SslCheckResult(domain="example.com", reachable=False)
        assert _threat_exposure_from_ssl("example.com", ssl_r) == []


# ---------------------------------------------------------------------------
# Vendor exposure
# ---------------------------------------------------------------------------


class TestVendorExposure:
    def test_no_vendors_returns_empty(self):
        assert _vendor_exposure_findings(_vendor_dict(reason="no_vendors")) == []

    def test_no_matches_returns_empty(self):
        assert _vendor_exposure_findings(_vendor_dict(total_matched=0)) == []

    def test_critical_cves_produce_critical_finding(self):
        findings = _vendor_exposure_findings(_vendor_dict(total_matched=5, critical=3))
        assert any(
            f.severity == "critical" and f.finding_type == "vendor_exposure" for f in findings
        )

    def test_high_cves_produce_high_finding(self):
        findings = _vendor_exposure_findings(_vendor_dict(total_matched=5, high=4))
        assert any(f.severity == "high" and f.finding_type == "vendor_exposure" for f in findings)

    def test_unmatched_vendors_produce_info_finding(self):
        findings = _vendor_exposure_findings(
            _vendor_dict(total_matched=2, critical=1, unmatched=["Cloudflare", "Okta"])
        )
        info = next((f for f in findings if f.severity == "info"), None)
        assert info is not None
        assert "Cloudflare" in info.description or "Okta" in info.description

    def test_upcoming_deadline_produces_high_finding(self):
        from datetime import UTC, datetime, timedelta

        due = (datetime.now(UTC) + timedelta(days=10)).isoformat()
        items = [{"vendor_name": "Microsoft", "due_date": due, "severity_label": "Critical"}]
        findings = _vendor_exposure_findings(_vendor_dict(total_matched=1, critical=1, items=items))
        assert any(
            f.severity == "high" and "vendors" in f.evidence and "count" in f.evidence
            for f in findings
        )


# ---------------------------------------------------------------------------
# Data gaps
# ---------------------------------------------------------------------------


class TestDataGapFindings:
    def test_no_missing_items_returns_empty(self):
        readiness = {"tier": "comprehensive", "items": _readiness_items()}
        assert _data_gap_findings(readiness) == []

    def test_missing_required_produces_medium(self):
        readiness = {"tier": "good", "items": _readiness_items(missing_keys=["vendors"])}
        findings = _data_gap_findings(readiness)
        assert any(f.severity == "medium" and f.finding_type == "data_gap" for f in findings)

    def test_missing_optional_produces_low(self):
        all_keys = ["org_name", "industry", "state", "employee_range", "vendors", "domains"]
        items = [{"key": k, "label": k, "complete": True, "required": True} for k in all_keys] + [
            {"key": "revenue", "label": "Revenue range", "complete": False, "required": False}
        ]
        readiness = {"tier": "good", "items": items}
        findings = _data_gap_findings(readiness)
        assert any(f.severity == "low" for f in findings)

    def test_minimal_tier_adds_high_finding(self):
        readiness = {
            "tier": "minimal",
            "items": _readiness_items(missing_keys=["vendors", "industry"]),
        }
        findings = _data_gap_findings(readiness)
        assert any(f.severity == "high" and "incomplete" in f.title.lower() for f in findings)

    def test_finding_type_is_data_gap(self):
        readiness = {"tier": "good", "items": _readiness_items(missing_keys=["state"])}
        findings = _data_gap_findings(readiness)
        assert all(f.finding_type == "data_gap" for f in findings)


# ---------------------------------------------------------------------------
# HTTP headers
# ---------------------------------------------------------------------------


class TestHttpHeaderFindings:
    def test_all_headers_present_no_findings(self):
        http = HttpHeaderResult(
            domain="example.com",
            reachable=True,
            has_hsts=True,
            has_csp=True,
            has_x_frame_options=True,
            has_x_content_type=True,
            has_permissions_policy=True,
        )
        assert _recommended_from_http_headers("example.com", http) == []

    def test_unreachable_no_findings(self):
        http = HttpHeaderResult(domain="example.com", reachable=False)
        assert _recommended_from_http_headers("example.com", http) == []

    def test_three_missing_headers_is_medium(self):
        http = HttpHeaderResult(
            domain="example.com",
            reachable=True,
            has_hsts=False,
            has_csp=False,
            has_x_frame_options=False,
        )
        findings = _recommended_from_http_headers("example.com", http)
        assert findings[0].severity == "medium"

    def test_one_missing_header_is_low(self):
        http = HttpHeaderResult(
            domain="example.com",
            reachable=True,
            has_hsts=False,
            has_csp=True,
            has_x_frame_options=True,
            has_x_content_type=True,
            has_permissions_policy=True,
        )
        findings = _recommended_from_http_headers("example.com", http)
        assert findings[0].severity == "low"

    def test_finding_type_is_recommended_action(self):
        http = HttpHeaderResult(domain="example.com", reachable=True, has_hsts=False)
        findings = _recommended_from_http_headers("example.com", http)
        assert findings[0].finding_type == "recommended_action"


# ---------------------------------------------------------------------------
# crt.sh findings
# ---------------------------------------------------------------------------


class TestCrtShFindings:
    def test_no_subdomains_no_finding(self):
        crt = CrtShResult(domain="example.com", subdomains=[], cert_count=5)
        assert _recommended_from_crtsh("example.com", crt) == []

    def test_error_no_finding(self):
        crt = CrtShResult(domain="example.com", error="timeout", subdomains=["sub.example.com"])
        assert _recommended_from_crtsh("example.com", crt) == []

    def test_few_subdomains_is_info(self):
        crt = CrtShResult(domain="example.com", subdomains=["a.example.com", "b.example.com"])
        findings = _recommended_from_crtsh("example.com", crt)
        assert findings[0].severity == "info"

    def test_many_subdomains_is_medium(self):
        subs = [f"sub{i}.example.com" for i in range(15)]
        crt = CrtShResult(domain="example.com", subdomains=subs)
        findings = _recommended_from_crtsh("example.com", crt)
        assert findings[0].severity == "medium"

    def test_finding_type_is_threat_exposure(self):
        crt = CrtShResult(domain="example.com", subdomains=["sub.example.com"])
        findings = _recommended_from_crtsh("example.com", crt)
        assert findings[0].finding_type == "threat_exposure"


# ---------------------------------------------------------------------------
# HIBP findings
# ---------------------------------------------------------------------------


class TestHibpFindings:
    def test_skipped_returns_empty(self):
        hibp = HibpResult(domain="example.com", skipped=True)
        assert _threat_from_hibp("example.com", hibp) == []

    def test_error_returns_empty(self):
        hibp = HibpResult(domain="example.com", error="rate limited")
        assert _threat_from_hibp("example.com", hibp) == []

    def test_zero_breaches_returns_empty(self):
        hibp = HibpResult(domain="example.com", breaches_found=0)
        assert _threat_from_hibp("example.com", hibp) == []

    def test_few_breaches_is_high(self):
        hibp = HibpResult(domain="example.com", breaches_found=2)
        findings = _threat_from_hibp("example.com", hibp)
        assert findings[0].severity == "high"

    def test_many_breaches_is_critical(self):
        hibp = HibpResult(domain="example.com", breaches_found=6)
        findings = _threat_from_hibp("example.com", hibp)
        assert findings[0].severity == "critical"

    def test_finding_type_is_threat_exposure(self):
        hibp = HibpResult(domain="example.com", breaches_found=1)
        findings = _threat_from_hibp("example.com", hibp)
        assert findings[0].finding_type == "threat_exposure"


# ---------------------------------------------------------------------------
# Recommendation synthesis
# ---------------------------------------------------------------------------


class TestSynthesizeRecommendations:
    def test_dns_finding_triggers_email_rec(self):
        dns_finding = _threat_exposure_from_dns(
            "example.com",
            DnsCheckResult(domain="example.com", spf_found=False, dmarc_found=False),
        )
        recs = _synthesize_recommendations(dns_finding)
        assert any(
            r.finding_type == "recommended_action"
            and r.evidence.get("dns_finding_count", 0) > 0
            for r in recs
        )

    def test_no_findings_returns_empty(self):
        assert _synthesize_recommendations([]) == []

    def test_critical_vendor_triggers_patch_rec(self):
        vendor_findings = _vendor_exposure_findings(_vendor_dict(total_matched=3, critical=2))
        recs = _synthesize_recommendations(vendor_findings)
        assert any("patch" in r.title.lower() for r in recs)

    def test_required_data_gaps_trigger_profile_rec(self):
        readiness = {"tier": "good", "items": _readiness_items(missing_keys=["vendors"])}
        gap_findings = _data_gap_findings(readiness)
        recs = _synthesize_recommendations(gap_findings)
        assert any("profile" in r.title.lower() or "complete" in r.title.lower() for r in recs)

    def test_all_recs_are_recommended_action_type(self):
        dns_findings = _threat_exposure_from_dns(
            "x.com", DnsCheckResult(domain="x.com", spf_found=False)
        )
        recs = _synthesize_recommendations(dns_findings)
        assert all(r.finding_type == "recommended_action" for r in recs)


# ---------------------------------------------------------------------------
# Security profile findings (Phase 3)
# ---------------------------------------------------------------------------


def _make_org(
    industry_label=None,
    security_controls=None,
    cloud_providers=None,
    compliance_frameworks=None,
    data_types=None,
    incident_history=None,
):
    org = MagicMock()
    org.industry_label = industry_label
    org.security_controls = security_controls
    org.cloud_providers = cloud_providers
    org.compliance_frameworks = compliance_frameworks
    org.data_types = data_types
    org.incident_history = incident_history
    return org


class TestSecurityProfileFindings:
    def test_no_controls_produces_data_gap(self):
        org = _make_org()
        findings = _analyze_security_profile(org)
        assert any(
            f.finding_type == "data_gap" and "security controls" in f.title.lower()
            for f in findings
        )

    def test_no_controls_data_gap_is_medium(self):
        org = _make_org()
        findings = _analyze_security_profile(org)
        gap = next(f for f in findings if "security controls" in f.title.lower())
        assert gap.severity == "medium"

    def test_control_no_produces_recommended_action(self):
        org = _make_org(security_controls={"mfa_enabled": "no"})
        findings = _analyze_security_profile(org)
        assert any(
            f.finding_type == "recommended_action" and "mfa" in f.title.lower() for f in findings
        )

    def test_control_no_preserves_severity(self):
        # mfa_enabled is "high" severity if "no"
        org = _make_org(security_controls={"mfa_enabled": "no"})
        findings = _analyze_security_profile(org)
        mfa = next(f for f in findings if "mfa" in f.title.lower())
        assert mfa.severity == "high"

    def test_control_unsure_downgrades_severity(self):
        # mfa_enabled is "high" if "no" → should be "medium" if "unsure"
        org = _make_org(security_controls={"mfa_enabled": "unsure"})
        findings = _analyze_security_profile(org)
        mfa = next(f for f in findings if "mfa" in f.title.lower())
        assert mfa.severity == "medium"

    def test_control_yes_produces_no_finding(self):
        from app.services.findings_engine import _SECURITY_CONTROLS_META

        all_yes = {key: "yes" for key, *_ in _SECURITY_CONTROLS_META}
        org = _make_org(security_controls=all_yes)
        findings = _analyze_security_profile(org)
        control_findings = [
            f
            for f in findings
            if f.source == "security_controls" and f.finding_type == "recommended_action"
        ]
        assert control_findings == []

    def test_healthcare_without_hipaa_is_high(self):
        org = _make_org(industry_label="Healthcare", compliance_frameworks=[])
        findings = _analyze_security_profile(org)
        assert any("HIPAA" in f.title and f.severity == "high" for f in findings)

    def test_healthcare_with_hipaa_no_compliance_gap(self):
        org = _make_org(industry_label="Healthcare", compliance_frameworks=["HIPAA"])
        findings = _analyze_security_profile(org)
        assert not any("HIPAA" in f.title and f.finding_type == "data_gap" for f in findings)

    def test_phi_without_hipaa_is_critical(self):
        org = _make_org(data_types=["PHI (health records)"], compliance_frameworks=[])
        findings = _analyze_security_profile(org)
        assert any("PHI" in f.title and f.severity == "critical" for f in findings)

    def test_payment_card_without_pci_is_high(self):
        org = _make_org(data_types=["Payment card data"], compliance_frameworks=[])
        findings = _analyze_security_profile(org)
        assert any("Payment card" in f.title and f.severity == "high" for f in findings)

    def test_incident_history_produces_threat_exposure(self):
        org = _make_org(incident_history="ransomware")
        findings = _analyze_security_profile(org)
        assert any(
            f.finding_type == "threat_exposure" and "ransomware" in f.title.lower()
            for f in findings
        )

    def test_incident_history_none_no_finding(self):
        org = _make_org(incident_history="none")
        findings = _analyze_security_profile(org)
        assert not any(f.source == "incident_history" for f in findings)

    def test_no_security_profile_data_returns_single_data_gap(self):
        # All fields None — should only get the "no controls reported" gap
        org = _make_org()
        findings = _analyze_security_profile(org)
        assert len(findings) == 1
        assert findings[0].finding_type == "data_gap"


# ---------------------------------------------------------------------------
# Tech fingerprint findings (Phase 6)
# ---------------------------------------------------------------------------


class TestTechFingerprintFindings:
    def test_no_detections_returns_empty(self):
        tech = TechFingerprintResult(domain="example.com", detected=[])
        assert _tech_fingerprint_findings("example.com", tech) == []

    def test_error_returns_empty(self):
        tech = TechFingerprintResult(domain="example.com", error="timeout")
        assert _tech_fingerprint_findings("example.com", tech) == []

    def test_detected_tech_produces_inventory_finding(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[{"name": "Nginx", "categories": ["Web Server"]}],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        inventory = [f for f in findings if "inventory" in f.id or f.severity == "info"]
        assert len(inventory) == 1
        assert inventory[0].finding_type == "threat_exposure"
        assert inventory[0].severity == "info"
        assert "Nginx" in inventory[0].description

    def test_wordpress_produces_risk_finding(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[
                {"name": "WordPress", "categories": ["CMS"]},
                {"name": "PHP", "categories": ["Programming Language"]},
            ],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        risk = [f for f in findings if f.finding_type == "recommended_action"]
        assert len(risk) == 1
        assert risk[0].severity == "medium"
        assert "WordPress" in risk[0].description

    def test_php_alone_produces_low_risk(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[{"name": "PHP", "categories": ["Programming Language"]}],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        risk = [f for f in findings if f.finding_type == "recommended_action"]
        assert len(risk) == 1
        assert risk[0].severity == "low"

    def test_safe_tech_no_risk_finding(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[{"name": "Cloudflare", "categories": ["CDN"]}],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        risk = [f for f in findings if f.finding_type == "recommended_action"]
        assert risk == []

    def test_source_is_tech_fingerprint(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[{"name": "React", "categories": ["Web Framework"]}],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        assert all(f.source == "tech_fingerprint" for f in findings)

    def test_only_one_risk_finding_per_domain(self):
        tech = TechFingerprintResult(
            domain="example.com",
            detected=[
                {"name": "WordPress", "categories": ["CMS"]},
                {"name": "PHP", "categories": ["Programming Language"]},
                {"name": "Microsoft IIS", "categories": ["Web Server"]},
            ],
        )
        findings = _tech_fingerprint_findings("example.com", tech)
        risk = [f for f in findings if f.finding_type == "recommended_action"]
        assert len(risk) == 1  # first match (WordPress) wins


# ---------------------------------------------------------------------------
# MITRE ATT&CK enrichment (Phase 6)
# ---------------------------------------------------------------------------


class TestMitreEnrichment:
    def test_ransomware_enrichment(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        ransomware = next((f for f in findings if "Ransomware" in f.title), None)
        assert ransomware is not None
        _enrich_finding_with_mitre(ransomware, "Ransomware")
        assert "mitre_techniques" in ransomware.evidence
        assert len(ransomware.evidence["mitre_techniques"]) > 0
        tech_ids = {t["id"] for t in ransomware.evidence["mitre_techniques"]}
        assert "T1486" in tech_ids  # Data Encrypted for Impact

    def test_bec_enrichment(self):
        findings = _threat_exposure_from_sector("Finance", "Finance & Insurance")
        bec = next((f for f in findings if "Business Email" in f.title), None)
        if bec is None:
            pytest.skip("BEC not in Finance sector findings")
        _enrich_finding_with_mitre(bec, "Business Email Compromise")
        assert "mitre_techniques" in bec.evidence

    def test_mitre_mitigations_attached(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        ransomware = next((f for f in findings if "Ransomware" in f.title), None)
        assert ransomware is not None
        _enrich_finding_with_mitre(ransomware, "Ransomware")
        assert "mitre_mitigations" in ransomware.evidence
        assert len(ransomware.evidence["mitre_mitigations"]) > 0

    def test_unknown_attack_type_no_enrichment(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        finding = findings[0]
        original_keys = set(finding.evidence.keys())
        _enrich_finding_with_mitre(finding, "NotARealAttackType")
        assert "mitre_techniques" not in finding.evidence
        assert set(finding.evidence.keys()) == original_keys

    def test_enrichment_techniques_have_required_fields(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        ransomware = next((f for f in findings if "Ransomware" in f.title), None)
        assert ransomware is not None
        _enrich_finding_with_mitre(ransomware, "Ransomware")
        for tech in ransomware.evidence["mitre_techniques"]:
            assert "id" in tech
            assert "name" in tech
            assert "tactic" in tech

    def test_enrichment_is_idempotent(self):
        findings = _threat_exposure_from_sector("Healthcare", "Healthcare")
        ransomware = next((f for f in findings if "Ransomware" in f.title), None)
        assert ransomware is not None
        _enrich_finding_with_mitre(ransomware, "Ransomware")
        count1 = len(ransomware.evidence["mitre_techniques"])
        _enrich_finding_with_mitre(ransomware, "Ransomware")
        count2 = len(ransomware.evidence["mitre_techniques"])
        assert count2 == count1


# ---------------------------------------------------------------------------
# Shodan host findings (Phase 6)
# ---------------------------------------------------------------------------


class TestShodanFindings:
    def test_skipped_returns_empty(self):
        shodan = ShodanHostResult(domain="example.com", skipped=True)
        assert _shodan_findings("example.com", shodan) == []

    def test_error_returns_empty(self):
        shodan = ShodanHostResult(domain="example.com", error="timeout")
        assert _shodan_findings("example.com", shodan) == []

    def test_no_ip_returns_empty(self):
        shodan = ShodanHostResult(domain="example.com")
        assert _shodan_findings("example.com", shodan) == []

    def test_risky_port_rdp_is_critical(self):
        shodan = ShodanHostResult(domain="example.com", ip="1.2.3.4", open_ports=[3389])
        findings = _shodan_findings("example.com", shodan)
        rdp = next((f for f in findings if "3389" in f.title), None)
        assert rdp is not None
        assert rdp.severity == "critical"
        assert rdp.finding_type == "threat_exposure"

    def test_risky_port_mysql_is_high(self):
        shodan = ShodanHostResult(domain="example.com", ip="1.2.3.4", open_ports=[3306])
        findings = _shodan_findings("example.com", shodan)
        mysql = next((f for f in findings if "3306" in f.title), None)
        assert mysql is not None
        assert mysql.severity == "high"

    def test_multiple_risky_ports(self):
        shodan = ShodanHostResult(domain="example.com", ip="1.2.3.4", open_ports=[23, 3389, 445])
        findings = _shodan_findings("example.com", shodan)
        port_findings = [
            f for f in findings if f.finding_type == "threat_exposure" and f.severity != "info"
        ]
        assert len(port_findings) == 3

    def test_vulns_produce_vendor_exposure(self):
        shodan = ShodanHostResult(
            domain="example.com",
            ip="1.2.3.4",
            open_ports=[80],
            vulns=["CVE-2024-1234", "CVE-2024-5678"],
        )
        findings = _shodan_findings("example.com", shodan)
        vuln_findings = [f for f in findings if f.finding_type == "vendor_exposure"]
        assert len(vuln_findings) == 1
        assert vuln_findings[0].severity == "high"  # < 5 CVEs

    def test_many_vulns_is_critical(self):
        cves = [f"CVE-2024-{i}" for i in range(7)]
        shodan = ShodanHostResult(
            domain="example.com",
            ip="1.2.3.4",
            open_ports=[80],
            vulns=cves,
        )
        findings = _shodan_findings("example.com", shodan)
        vuln_findings = [f for f in findings if f.finding_type == "vendor_exposure"]
        assert vuln_findings[0].severity == "critical"

    def test_safe_ports_produce_info_inventory(self):
        shodan = ShodanHostResult(
            domain="example.com",
            ip="1.2.3.4",
            open_ports=[80, 443],
        )
        findings = _shodan_findings("example.com", shodan)
        assert len(findings) == 1
        assert findings[0].severity == "info"
        assert findings[0].finding_type == "threat_exposure"

    def test_source_is_shodan(self):
        shodan = ShodanHostResult(
            domain="example.com",
            ip="1.2.3.4",
            open_ports=[3389],
        )
        findings = _shodan_findings("example.com", shodan)
        assert all(f.source == "shodan" for f in findings)

    def test_finding_ids_are_deterministic(self):
        shodan = ShodanHostResult(
            domain="example.com",
            ip="1.2.3.4",
            open_ports=[3389],
        )
        f1 = _shodan_findings("example.com", shodan)
        f2 = _shodan_findings("example.com", shodan)
        assert [f.id for f in f1] == [f.id for f in f2]


# ---------------------------------------------------------------------------
# AlienVault OTX findings (Phase 6)
# ---------------------------------------------------------------------------


class TestOtxFindings:
    def test_skipped_returns_empty(self):
        otx = OtxResult(domain="example.com", skipped=True)
        assert _otx_findings("example.com", otx) == []

    def test_error_returns_empty(self):
        otx = OtxResult(domain="example.com", error="API error")
        assert _otx_findings("example.com", otx) == []

    def test_zero_pulses_returns_empty(self):
        otx = OtxResult(domain="example.com", pulse_count=0)
        assert _otx_findings("example.com", otx) == []

    def test_few_pulses_is_medium(self):
        otx = OtxResult(domain="example.com", pulse_count=1)
        findings = _otx_findings("example.com", otx)
        assert len(findings) == 1
        assert findings[0].severity == "medium"

    def test_moderate_pulses_is_high(self):
        otx = OtxResult(domain="example.com", pulse_count=5)
        findings = _otx_findings("example.com", otx)
        assert findings[0].severity == "high"

    def test_many_pulses_is_critical(self):
        otx = OtxResult(domain="example.com", pulse_count=15)
        findings = _otx_findings("example.com", otx)
        assert findings[0].severity == "critical"

    def test_malware_families_in_description(self):
        otx = OtxResult(
            domain="example.com",
            pulse_count=3,
            malware_families=["Emotet", "TrickBot"],
        )
        findings = _otx_findings("example.com", otx)
        assert "Emotet" in findings[0].description

    def test_finding_type_is_threat_exposure(self):
        otx = OtxResult(domain="example.com", pulse_count=2)
        findings = _otx_findings("example.com", otx)
        assert findings[0].finding_type == "threat_exposure"

    def test_source_is_otx(self):
        otx = OtxResult(domain="example.com", pulse_count=2)
        findings = _otx_findings("example.com", otx)
        assert findings[0].source == "otx"

    def test_evidence_includes_pulse_count(self):
        otx = OtxResult(domain="example.com", pulse_count=7, reputation_score=42)
        findings = _otx_findings("example.com", otx)
        assert findings[0].evidence["pulse_count"] == 7
        assert findings[0].evidence["reputation_score"] == 42

    def test_boundary_3_pulses_is_high(self):
        otx = OtxResult(domain="example.com", pulse_count=3)
        findings = _otx_findings("example.com", otx)
        assert findings[0].severity == "high"

    def test_boundary_10_pulses_is_critical(self):
        otx = OtxResult(domain="example.com", pulse_count=10)
        findings = _otx_findings("example.com", otx)
        assert findings[0].severity == "critical"


# ---------------------------------------------------------------------------
# FindingsEngine integration (mocked DB)
# ---------------------------------------------------------------------------


class TestFindingsEngineIntegration:
    @pytest.mark.asyncio
    async def test_build_returns_report(self):
        """Engine returns a FindingsReport with the right org_id."""
        from app.schemas.assessment_readiness import AssessmentReadinessResponse, ReadinessItem
        from app.schemas.vendor_alert import SeverityBreakdown, VendorAlertsResponse

        org = MagicMock()
        org.id = 42
        org.name = "Test Corp"
        org.industry_label = "Healthcare"
        org.employee_range = "11-50"
        org.primary_state = "CA"
        org.primary_domain = None  # skip domain checks
        org.security_controls = None
        org.cloud_providers = None
        org.compliance_frameworks = None
        org.data_types = None
        org.incident_history = None

        # Mock DB session — no domains
        mock_session = AsyncMock()
        domain_rows = MagicMock()
        domain_rows.all.return_value = []
        mock_session.execute.return_value = domain_rows

        readiness_response = AssessmentReadinessResponse(
            is_ready=True,
            readiness_pct=100.0,
            tier="good",
            items=[
                ReadinessItem(
                    key="org_name",
                    label="Org Name",
                    complete=True,
                    required=True,
                    detail="Test Corp",
                ),
                ReadinessItem(
                    key="industry",
                    label="Industry",
                    complete=True,
                    required=True,
                    detail="Healthcare",
                ),
                ReadinessItem(
                    key="state", label="State", complete=True, required=True, detail="CA"
                ),
                ReadinessItem(
                    key="employee_range",
                    label="Employees",
                    complete=True,
                    required=True,
                    detail="11-50",
                ),
                ReadinessItem(
                    key="vendors",
                    label="Vendors",
                    complete=True,
                    required=True,
                    detail="2 vendor(s)",
                ),
                ReadinessItem(
                    key="domains",
                    label="Domains",
                    complete=True,
                    required=True,
                    detail="1 domain(s)",
                ),
            ],
            next_steps=[],
        )

        vendor_response = VendorAlertsResponse(
            total_matched=0,
            severity_breakdown=SeverityBreakdown(),
            items=[],
            page=1,
            page_size=100,
            unmatched_vendors=[],
            reason="no_matches",
            kev_last_ingest_at=None,
        )

        with (
            patch(
                "app.services.findings_engine.evaluate_readiness",
                new=AsyncMock(return_value=readiness_response),
            ),
            patch(
                "app.services.findings_engine.VendorAlertService.get_alerts",
                new=AsyncMock(return_value=vendor_response),
            ),
        ):
            engine = FindingsEngine(mock_session)
            report = await engine.build(org)

        assert report.org_id == 42
        assert isinstance(report.findings, list)
        assert report.summary.total == len(report.findings)
        assert report.assessment_tier == "good"

    @pytest.mark.asyncio
    async def test_findings_sorted_by_severity(self):
        """Critical findings appear before high, high before medium, etc."""
        from app.schemas.assessment_readiness import AssessmentReadinessResponse, ReadinessItem
        from app.schemas.vendor_alert import SeverityBreakdown, VendorAlertsResponse

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        org = MagicMock()
        org.id = 1
        org.name = "SortTest"
        org.industry_label = "Finance & Insurance"
        org.employee_range = "201-500"
        org.primary_state = "NY"
        org.primary_domain = None
        org.security_controls = None
        org.cloud_providers = None
        org.compliance_frameworks = None
        org.data_types = None
        org.incident_history = None

        mock_session = AsyncMock()
        domain_rows = MagicMock()
        domain_rows.all.return_value = []
        mock_session.execute.return_value = domain_rows

        readiness_response = AssessmentReadinessResponse(
            is_ready=True,
            readiness_pct=75.0,
            tier="good",
            items=[
                ReadinessItem(key=k, label=k, complete=True, required=True, detail=k)
                for k in ["org_name", "industry", "state", "employee_range", "vendors", "domains"]
            ],
            next_steps=[],
        )
        vendor_response = VendorAlertsResponse(
            total_matched=5,
            severity_breakdown=SeverityBreakdown(critical=3, high=2),
            items=[],
            page=1,
            page_size=100,
            unmatched_vendors=[],
            reason=None,
            kev_last_ingest_at=None,
        )

        with (
            patch(
                "app.services.findings_engine.evaluate_readiness",
                new=AsyncMock(return_value=readiness_response),
            ),
            patch(
                "app.services.findings_engine.VendorAlertService.get_alerts",
                new=AsyncMock(return_value=vendor_response),
            ),
        ):
            report = await FindingsEngine(mock_session).build(org)

        severities = [severity_order.get(f.severity, 99) for f in report.findings]
        assert severities == sorted(severities), "Findings are not sorted by severity"


# ---------------------------------------------------------------------------
# match_confidence on vendor exposure findings
# ---------------------------------------------------------------------------


class TestVendorExposureConfidence:
    """_vendor_exposure_findings handles items with any match_confidence value."""

    def test_exact_match_items_produce_vendor_findings(self):
        data = _vendor_dict(
            total_matched=1,
            critical=1,
            items=[{"vendor_name": "Microsoft", "due_date": None, "match_confidence": 1.0}],
        )
        findings = _vendor_exposure_findings(data)
        assert any(f.finding_type == "vendor_exposure" for f in findings)

    def test_fuzzy_match_items_also_produce_vendor_findings(self):
        data = _vendor_dict(
            total_matched=1,
            high=1,
            items=[{"vendor_name": "Microsft", "due_date": None, "match_confidence": 0.82}],
        )
        findings = _vendor_exposure_findings(data)
        assert any(f.finding_type == "vendor_exposure" for f in findings)

    def test_none_confidence_does_not_crash(self):
        # match_confidence=None (legacy rows or exact path before schema update)
        data = _vendor_dict(
            total_matched=1,
            high=1,
            items=[{"vendor_name": "Apache", "due_date": None, "match_confidence": None}],
        )
        findings = _vendor_exposure_findings(data)
        assert len(findings) >= 1

    def test_zero_total_matched_returns_empty_regardless_of_confidence(self):
        data = _vendor_dict(
            total_matched=0,
            items=[{"vendor_name": "Cisco", "due_date": None, "match_confidence": 0.9}],
        )
        findings = _vendor_exposure_findings(data)
        assert findings == []

    def test_finding_schema_accepts_match_confidence_field(self):
        from app.schemas.findings import Finding

        f = Finding(
            id="test-id",
            finding_type="vendor_exposure",
            severity="high",
            title="Test",
            description="desc",
            evidence={},
            source="kev_vendor_match",
            affected_assets=[],
            match_confidence=0.85,
        )
        assert f.match_confidence == pytest.approx(0.85)

    def test_finding_schema_match_confidence_defaults_none(self):
        from app.schemas.findings import Finding

        f = Finding(
            id="test-id",
            finding_type="vendor_exposure",
            severity="high",
            title="Test",
            description="desc",
            evidence={},
            source="kev_vendor_match",
            affected_assets=[],
        )
        assert f.match_confidence is None
