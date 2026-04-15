"""End-to-end integration tests for Findings + AI Summary pipelines.

Tests the full service pipeline: FindingsEngine.build() and
AISummaryService.build() with mocked upstream services. Validates that
the report schemas are correct, categories/severities are consistent,
and error paths behave properly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.findings import Finding, FindingsReport, FindingsSummary
from app.schemas.ai_summary import AISummaryResponse
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
from app.services.findings_engine import FindingsEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_org(
    *,
    org_id=1,
    name="Acme Corp",
    industry="information",
    industry_label="Information",
    ic3_sector="Information",
    primary_state="CA",
    employee_range="51-200",
    primary_domain="acme.com",
    revenue_range="$1M-$10M",
    security_controls=None,
    compliance_frameworks=None,
    data_types=None,
    incident_history=None,
):
    org = MagicMock()
    org.id = org_id
    org.name = name
    org.industry = industry
    org.industry_label = industry_label
    org.ic3_sector = ic3_sector
    org.primary_state = primary_state
    org.employee_range = employee_range
    org.primary_domain = primary_domain
    org.revenue_range = revenue_range
    org.security_controls = security_controls
    org.compliance_frameworks = compliance_frameworks
    org.data_types = data_types
    org.incident_history = incident_history
    return org


def _mock_db(domains=None):
    """Create a mock AsyncSession with a canned domain query response."""
    db = AsyncMock()
    domain_rows = [(d,) for d in (domains or [])]
    result_mock = MagicMock()
    result_mock.all.return_value = domain_rows
    db.execute = AsyncMock(return_value=result_mock)
    return db


@dataclass
class _ReadinessItem:
    key: str
    label: str
    complete: bool
    required: bool


def _readiness_items_all_complete():
    keys = [
        ("org_name", "Organization Name"),
        ("industry", "Industry"),
        ("state", "State"),
        ("employee_range", "Employee Range"),
        ("vendors", "Vendors"),
        ("domains", "Domains"),
    ]
    return [_ReadinessItem(key=k, label=l, complete=True, required=True) for k, l in keys]


def _good_readiness(tier="good", readiness_pct=100):
    return MagicMock(
        tier=tier,
        is_ready=True,
        readiness_pct=readiness_pct,
        items=_readiness_items_all_complete(),
        next_steps=[],
    )


def _vendor_alerts_response(total=5, critical=2, high=1, medium=1, low=1, items=None):
    resp = MagicMock()
    resp.total_matched = total
    sb = MagicMock()
    sb.critical = critical
    sb.high = high
    sb.medium = medium
    sb.low = low
    resp.severity_breakdown = sb
    resp.unmatched_vendors = []
    resp.reason = None
    resp.items = items or []
    return resp


def _dns_ok():
    return DnsCheckResult(
        domain="acme.com", spf_found=True, spf_record="v=spf1 include:_spf.google.com ~all",
        dmarc_found=True, dmarc_policy="reject", dmarc_record="v=DMARC1; p=reject",
        dkim_selector_found=True, error=None,
    )


def _dns_missing_all():
    return DnsCheckResult(
        domain="acme.com", spf_found=False, spf_record=None,
        dmarc_found=False, dmarc_policy=None, dmarc_record=None,
        dkim_selector_found=False, error=None,
    )


def _http_ok():
    return HttpHeaderResult(
        domain="acme.com", reachable=True, has_hsts=True, has_csp=True,
        has_x_frame_options=True, has_x_content_type=True, has_permissions_policy=True,
        status_code=200, error=None,
    )


def _http_missing_headers():
    return HttpHeaderResult(
        domain="acme.com", reachable=True, has_hsts=False, has_csp=False,
        has_x_frame_options=False, has_x_content_type=False, has_permissions_policy=False,
        status_code=200, error=None,
    )


def _ssl_ok():
    return SslCheckResult(
        domain="acme.com", reachable=True, issuer="Let's Encrypt",
        expiry=datetime(2025, 6, 1, tzinfo=timezone.utc), days_until_expiry=90,
        self_signed=False, tls_version="TLSv1.3", error=None,
    )


def _ssl_expiring():
    return SslCheckResult(
        domain="acme.com", reachable=True, issuer="Let's Encrypt",
        expiry=datetime(2024, 5, 1, tzinfo=timezone.utc), days_until_expiry=10,
        self_signed=False, tls_version="TLSv1.2", error=None,
    )


def _crtsh_empty():
    return CrtShResult(domain="acme.com", subdomains=[], cert_count=0, error=None)


def _hibp_clean():
    return HibpResult(domain="acme.com", breaches_found=0, breach_names=[], error=None, skipped=False)


def _tech_clean():
    return TechFingerprintResult(domain="acme.com", detected=[], error=None)


def _tech_wordpress():
    return TechFingerprintResult(
        domain="acme.com",
        detected=[
            {"name": "WordPress", "categories": ["CMS"]},
            {"name": "PHP", "categories": ["Programming Language"]},
            {"name": "Nginx", "categories": ["Web Server"]},
        ],
    )


def _shodan_clean():
    return ShodanHostResult(domain="acme.com", skipped=True)


def _shodan_risky():
    return ShodanHostResult(
        domain="acme.com", ip="93.184.216.34",
        open_ports=[22, 80, 443, 3389, 27017],
        vulns=["CVE-2024-1234", "CVE-2024-5678"],
        isp="Edgecast",
    )


def _otx_clean():
    return OtxResult(domain="acme.com", skipped=True)


def _otx_flagged():
    return OtxResult(
        domain="acme.com", pulse_count=5,
        malware_families=["Emotet"], reputation_score=30,
    )


def _risk_score():
    m = MagicMock()
    m.score = 65.0
    m.label = "Moderate"
    return m


class _PatchCtx:
    """Context manager that patches all FindingsEngine upstream dependencies."""

    def __init__(self, *, readiness=None, risk_score=None, vendor_resp=None,
                 tier1=None, tier2=None):
        self._readiness = readiness or _good_readiness()
        self._risk_score = risk_score or _risk_score()
        self._vendor_resp = vendor_resp or _vendor_alerts_response()
        self._tier1 = tier1 or (_dns_missing_all(), _http_missing_headers(), _ssl_ok(), _tech_clean())
        self._tier2 = tier2 or (_crtsh_empty(), _hibp_clean(), _shodan_clean(), _otx_clean())
        self._patches = []

    def __enter__(self):
        self._patches = [
            patch("app.services.findings_engine.evaluate_readiness", new_callable=AsyncMock, return_value=self._readiness),
            patch("app.services.findings_engine.calculate_smb_risk_score", return_value=self._risk_score),
            patch("app.services.findings_engine.VendorAlertService"),
            patch("app.services.findings_engine.run_tier1_checks", new_callable=AsyncMock, return_value=self._tier1),
            patch("app.services.findings_engine.run_tier2_checks", new_callable=AsyncMock, return_value=self._tier2),
        ]
        self._mocks = [p.__enter__() for p in self._patches]
        self._mocks[2].return_value.get_alerts = AsyncMock(return_value=self._vendor_resp)
        return self

    def __exit__(self, *args):
        for p in reversed(self._patches):
            p.__exit__(*args)


def _patch_engine(**kwargs):
    return _PatchCtx(**kwargs)


# ---------------------------------------------------------------------------
# FindingsEngine.build() — full pipeline
# ---------------------------------------------------------------------------


class TestFindingsEnginePipeline:
    """Integration tests for FindingsEngine.build() with mocked upstreams."""

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_valid_report(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine():
            report = await FindingsEngine(db).build(org)

        assert isinstance(report, FindingsReport)
        assert report.org_id == 1
        assert report.summary.total == len(report.findings)
        assert report.summary.total > 0
        assert report.generated_at
        assert len(report.data_sources_used) > 0

    @pytest.mark.asyncio
    async def test_all_finding_types_present_with_gaps(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine():
            report = await FindingsEngine(db).build(org)

        types_found = {f.finding_type for f in report.findings}
        assert "threat_exposure" in types_found
        assert "vendor_exposure" in types_found
        assert "recommended_action" in types_found

    @pytest.mark.asyncio
    async def test_severities_are_valid(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean())):
            report = await FindingsEngine(db).build(org)

        valid_severities = {"critical", "high", "medium", "low", "info"}
        for f in report.findings:
            assert f.severity in valid_severities, f"Invalid severity: {f.severity}"

    @pytest.mark.asyncio
    async def test_summary_counts_match(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(tier1=(_dns_missing_all(), _http_missing_headers(), _ssl_expiring(), _tech_clean())):
            report = await FindingsEngine(db).build(org)

        assert sum(report.summary.by_type.values()) == report.summary.total
        assert sum(report.summary.by_severity.values()) == report.summary.total

    @pytest.mark.asyncio
    async def test_finding_ids_are_unique(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine():
            report = await FindingsEngine(db).build(org)

        ids = [f.id for f in report.findings]
        assert len(ids) == len(set(ids)), "Duplicate finding IDs detected"

    @pytest.mark.asyncio
    async def test_findings_have_nonempty_fields(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine():
            report = await FindingsEngine(db).build(org)

        for f in report.findings:
            assert f.id, "Finding has empty id"
            assert f.title, "Finding has empty title"
            assert f.description, "Finding has empty description"
            assert f.source, "Finding has empty source"

    @pytest.mark.asyncio
    async def test_ssl_expiring_produces_threat_finding(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_expiring(), _tech_clean()),
            vendor_resp=_vendor_alerts_response(total=0, critical=0, high=0, medium=0, low=0),
        ):
            report = await FindingsEngine(db).build(org)

        ssl_findings = [
            f for f in report.findings
            if "ssl" in f.source.lower() or "cert" in f.title.lower()
            or "tls" in f.title.lower() or "expir" in f.title.lower()
        ]
        assert len(ssl_findings) > 0, "Expected SSL/cert finding for expiring certificate"

    @pytest.mark.asyncio
    async def test_no_vendor_matches_still_produces_report(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean()),
            vendor_resp=_vendor_alerts_response(total=0, critical=0, high=0, medium=0, low=0),
        ):
            report = await FindingsEngine(db).build(org)

        assert isinstance(report, FindingsReport)
        assert report.summary.total >= 0

    @pytest.mark.asyncio
    async def test_dns_missing_produces_threat_findings(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(tier1=(_dns_missing_all(), _http_ok(), _ssl_ok(), _tech_clean())):
            report = await FindingsEngine(db).build(org)

        dns_findings = [
            f for f in report.findings
            if "spf" in f.title.lower() or "dmarc" in f.title.lower() or "dns" in f.source.lower()
        ]
        assert len(dns_findings) > 0, "Expected DNS findings for missing records"

    @pytest.mark.asyncio
    async def test_http_missing_headers_produces_recommendations(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(tier1=(_dns_ok(), _http_missing_headers(), _ssl_ok(), _tech_clean())):
            report = await FindingsEngine(db).build(org)

        http_findings = [
            f for f in report.findings
            if "header" in f.source.lower() or "hsts" in f.title.lower() or "csp" in f.title.lower()
        ]
        assert len(http_findings) > 0, "Expected HTTP header findings for missing headers"

    @pytest.mark.asyncio
    async def test_no_domain_skips_domain_checks(self):
        db = _mock_db()
        org = _mock_org(primary_domain=None)

        with _patch_engine():
            report = await FindingsEngine(db).build(org)

        assert isinstance(report, FindingsReport)
        domain_sources = {"dns_checks", "http_header_checks", "ssl_checks", "crtsh", "hibp"}
        for src in domain_sources:
            assert src not in report.data_sources_used


# ---------------------------------------------------------------------------
# Phase 6 integration: Tech fingerprint, Shodan, OTX in full pipeline
# ---------------------------------------------------------------------------


class TestPhase6Integration:
    """Verify Phase 6 sources flow through the full pipeline."""

    @pytest.mark.asyncio
    async def test_tech_fingerprint_findings_in_report(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_wordpress()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_clean(), _otx_clean()),
        ):
            report = await FindingsEngine(db).build(org)

        tech_findings = [f for f in report.findings if f.source == "tech_fingerprint"]
        assert len(tech_findings) >= 1
        assert "tech_fingerprint" in report.data_sources_used
        inventory = [f for f in tech_findings if f.severity == "info"]
        assert len(inventory) == 1
        assert "WordPress" in inventory[0].description

    @pytest.mark.asyncio
    async def test_shodan_findings_in_report(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_risky(), _otx_clean()),
        ):
            report = await FindingsEngine(db).build(org)

        shodan_findings = [f for f in report.findings if f.source == "shodan"]
        assert len(shodan_findings) >= 1
        assert "shodan" in report.data_sources_used
        rdp = [f for f in shodan_findings if "3389" in f.title]
        assert len(rdp) == 1
        assert rdp[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_otx_findings_in_report(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_clean(), _otx_flagged()),
        ):
            report = await FindingsEngine(db).build(org)

        otx_findings = [f for f in report.findings if f.source == "otx"]
        assert len(otx_findings) == 1
        assert otx_findings[0].severity == "high"
        assert "otx" in report.data_sources_used

    @pytest.mark.asyncio
    async def test_mitre_enrichment_in_sector_findings(self):
        db = _mock_db()
        org = _mock_org(industry_label="Healthcare", ic3_sector="Healthcare")

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_clean(), _otx_clean()),
        ):
            report = await FindingsEngine(db).build(org)

        sector_threats = [
            f for f in report.findings
            if f.source == "ic3_sector_weights" and f.finding_type == "threat_exposure"
        ]
        enriched = [f for f in sector_threats if "mitre_techniques" in f.evidence]
        assert len(enriched) > 0
        assert "mitre_attack" in report.data_sources_used

    @pytest.mark.asyncio
    async def test_all_phase6_sources_together(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_wordpress()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_risky(), _otx_flagged()),
        ):
            report = await FindingsEngine(db).build(org)

        sources = set(report.data_sources_used)
        assert "tech_fingerprint" in sources
        assert "shodan" in sources
        assert "otx" in sources
        assert "mitre_attack" in sources

        finding_sources = {f.source for f in report.findings}
        assert "tech_fingerprint" in finding_sources
        assert "shodan" in finding_sources
        assert "otx" in finding_sources

    @pytest.mark.asyncio
    async def test_skipped_apis_produce_no_findings(self):
        db = _mock_db()
        org = _mock_org()

        with _patch_engine(
            tier1=(_dns_ok(), _http_ok(), _ssl_ok(), _tech_clean()),
            tier2=(_crtsh_empty(), _hibp_clean(), _shodan_clean(), _otx_clean()),
        ):
            report = await FindingsEngine(db).build(org)

        assert not any(f.source == "shodan" for f in report.findings)
        assert not any(f.source == "otx" for f in report.findings)


# ---------------------------------------------------------------------------
# AISummaryService.build() — full pipeline
# ---------------------------------------------------------------------------


class TestAISummaryPipeline:
    """Integration tests for AISummaryService."""

    @pytest.mark.asyncio
    async def test_fallback_when_gemini_key_empty(self):
        from app.services.ai_summary import AISummaryService

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1,
            findings=[
                Finding(
                    id="abc123", finding_type="threat_exposure", severity="high",
                    title="BEC exposure", description="Your sector is targeted by BEC.",
                    evidence={"weight": 0.3}, source="ic3", affected_assets=["Information"],
                ),
            ],
            summary=FindingsSummary(total=1, by_type={"threat_exposure": 1}, by_severity={"high": 1}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=["ic3"],
            assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
        ):
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result = await svc.build(org)

        assert isinstance(result, AISummaryResponse)
        assert result.ai_generated is False
        assert result.model_used is None
        assert len(result.narrative) > 0
        assert result.disclaimer

    @pytest.mark.asyncio
    async def test_response_schema_completeness(self):
        from app.services.ai_summary import AISummaryService

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=[], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
        ):
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result = await svc.build(org)

        assert result.narrative is not None
        assert isinstance(result.ai_generated, bool)
        assert isinstance(result.findings_count, int)
        assert isinstance(result.risk_score, float)
        assert result.risk_label in {"Critical", "High", "Moderate", "Low"}
        assert result.generated_at
        assert isinstance(result.cached, bool)
        assert result.disclaimer

    @pytest.mark.asyncio
    async def test_caching_second_call(self):
        import app.services.ai_summary as ai_mod
        from app.services.ai_summary import AISummaryService

        # Clear module-level cache to isolate test
        ai_mod._cache.clear()

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=[], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
        ):
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result1 = await svc.build(org)
            result2 = await svc.build(org)

        assert result1.cached is False
        assert result2.cached is True

        # Clean up
        ai_mod._cache.clear()

    @pytest.mark.asyncio
    async def test_gemini_failure_falls_back_to_template(self):
        import app.services.ai_summary as ai_mod
        from app.services.ai_summary import AISummaryService

        ai_mod._cache.clear()

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1,
            findings=[
                Finding(
                    id="test1", finding_type="threat_exposure", severity="critical",
                    title="Critical threat", description="A critical threat.",
                    evidence={}, source="test", affected_assets=[],
                ),
            ],
            summary=FindingsSummary(total=1, by_type={"threat_exposure": 1}, by_severity={"critical": 1}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=["test"], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
            patch("app.services.ai_summary._call_gemini", new_callable=AsyncMock, side_effect=RuntimeError("API down")),
        ):
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result = await svc.build(org)

        assert result.ai_generated is False
        assert result.model_used is None
        assert len(result.narrative) > 0
        assert result.risk_score == 65.0

        ai_mod._cache.clear()

    @pytest.mark.asyncio
    async def test_ai_disabled_uses_fallback(self):
        import app.services.ai_summary as ai_mod
        from app.services.ai_summary import AISummaryService

        ai_mod._cache.clear()

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=[], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
        ):
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = False  # kill switch off

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result = await svc.build(org)

        assert result.ai_generated is False
        assert result.model_used is None

        ai_mod._cache.clear()

    @pytest.mark.asyncio
    async def test_gemini_success_marks_ai_generated(self):
        import app.services.ai_summary as ai_mod
        from app.services.ai_summary import AISummaryService

        ai_mod._cache.clear()

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=[], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
            patch("app.services.ai_summary._call_gemini", new_callable=AsyncMock, return_value="AI-generated summary text here."),
        ):
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result = await svc.build(org)

        assert result.ai_generated is True
        assert result.model_used == "gemini-2.5-flash"
        assert result.narrative == "AI-generated summary text here."

        ai_mod._cache.clear()

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        import app.services.ai_summary as ai_mod
        from app.services.ai_summary import AISummaryService

        ai_mod._cache.clear()

        db = _mock_db()
        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at=datetime.utcnow().isoformat(),
            data_sources_used=[], assessment_tier="good",
        )

        with (
            patch("app.services.ai_summary.FindingsEngine") as mock_engine_cls,
            patch("app.services.ai_summary.calculate_smb_risk_score", return_value=_risk_score()),
            patch("app.services.ai_summary.settings") as mock_settings,
        ):
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.AI_SUMMARY_CACHE_TTL = 3600
            mock_settings.AI_SUMMARY_ENABLED = True

            mock_engine_cls.return_value.build = AsyncMock(return_value=report)

            svc = AISummaryService(db)
            result1 = await svc.build(org)
            assert result1.cached is False

            svc.invalidate(org.id)

            result2 = await svc.build(org)
            assert result2.cached is False  # not cached after invalidation

        ai_mod._cache.clear()


# ---------------------------------------------------------------------------
# AI Summary prompt building
# ---------------------------------------------------------------------------


class TestAISummaryPromptBuilding:
    """Test prompt construction and fallback narrative generation."""

    def test_prompt_contains_org_context(self):
        from app.services.ai_summary import _build_prompt

        org = _mock_org(name="TestCorp", industry_label="Healthcare", employee_range="51-200")
        report = FindingsReport(
            org_id=1,
            findings=[
                Finding(
                    id="f1", finding_type="threat_exposure", severity="high",
                    title="BEC threat", description="Business email compromise risk.",
                    evidence={}, source="ic3", affected_assets=[],
                ),
            ],
            summary=FindingsSummary(total=1, by_type={"threat_exposure": 1}, by_severity={"high": 1}),
            generated_at="2024-01-01T00:00:00",
            data_sources_used=["ic3"], assessment_tier="good",
        )
        prompt = _build_prompt(org, report, 65.0)

        assert "TestCorp" in prompt
        assert "Healthcare" in prompt
        assert "51-200" in prompt
        assert "65" in prompt
        assert "BEC threat" in prompt

    def test_prompt_caps_findings_at_20(self):
        from app.services.ai_summary import _build_prompt

        org = _mock_org()
        findings = [
            Finding(
                id=f"f{i}", finding_type="threat_exposure", severity="medium",
                title=f"Finding {i}", description=f"Description {i}.",
                evidence={}, source="test", affected_assets=[],
            )
            for i in range(30)
        ]
        report = FindingsReport(
            org_id=1, findings=findings,
            summary=FindingsSummary(total=30, by_type={"threat_exposure": 30}, by_severity={"medium": 30}),
            generated_at="2024-01-01T00:00:00",
            data_sources_used=["test"], assessment_tier="good",
        )
        prompt = _build_prompt(org, report, 50.0)

        assert "Finding 19" in prompt  # 0-indexed, finding #19 is last of 20
        assert "Finding 20" not in prompt  # #20 would be the 21st

    def test_fallback_narrative_includes_risk_info(self):
        from app.services.ai_summary import _build_fallback

        org = _mock_org(name="Acme Corp", industry_label="Information")
        report = FindingsReport(
            org_id=1,
            findings=[
                Finding(
                    id="f1", finding_type="threat_exposure", severity="critical",
                    title="Critical exposure", description="Critical desc.",
                    evidence={}, source="test", affected_assets=[],
                ),
            ],
            summary=FindingsSummary(total=1, by_type={"threat_exposure": 1}, by_severity={"critical": 1}),
            generated_at="2024-01-01T00:00:00",
            data_sources_used=["test"], assessment_tier="good",
        )
        narrative = _build_fallback(org, report, 72.0)

        assert "Acme Corp" in narrative
        assert "72" in narrative
        assert "Critical exposure" in narrative

    def test_fallback_with_no_findings(self):
        from app.services.ai_summary import _build_fallback

        org = _mock_org()
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at="2024-01-01T00:00:00",
            data_sources_used=[], assessment_tier="good",
        )
        narrative = _build_fallback(org, report, 30.0)

        assert "0 findings" in narrative
        assert "Low" in narrative


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """Verify Pydantic schemas enforce constraints."""

    def test_finding_schema_roundtrip(self):
        f = Finding(
            id="abc123def456", finding_type="threat_exposure", severity="high",
            title="Test finding", description="Test description",
            evidence={"key": "value"}, source="test", affected_assets=["asset1"],
        )
        data = f.model_dump()
        assert Finding(**data) == f

    def test_findings_report_schema_roundtrip(self):
        report = FindingsReport(
            org_id=1, findings=[],
            summary=FindingsSummary(total=0, by_type={}, by_severity={}),
            generated_at="2024-01-01T00:00:00",
            data_sources_used=["test"], assessment_tier="good",
        )
        data = report.model_dump()
        assert FindingsReport(**data) == report

    def test_ai_summary_schema_roundtrip(self):
        summary = AISummaryResponse(
            narrative="Test narrative", ai_generated=False, model_used=None,
            findings_count=0, risk_score=50.0, risk_label="Moderate",
            generated_at="2024-01-01T00:00:00", cached=False,
            disclaimer="Test disclaimer",
        )
        data = summary.model_dump()
        assert AISummaryResponse(**data) == summary
