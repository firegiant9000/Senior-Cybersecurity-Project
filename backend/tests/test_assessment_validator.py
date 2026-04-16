"""Unit tests for the assessment validation engine.

These tests call the service functions directly with in-memory objects —
no HTTP layer, no real DB required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.org_domain import OrgDomain
from app.db.org_vendor import OrgVendor
from app.db.organization import Organization
from app.services.assessment_validator import run_validation

# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(**kwargs) -> Organization:
    defaults = {
        "id": 1,
        "name": "Acme Corp",
        "industry_label": "Technology",
        "ic3_sector": "Technology",
        "primary_state": "CA",
        "employee_range": "11-50",
        "revenue_range": "$1M-$10M",
        "security_controls": {"mfa_enabled": "yes"},
        "cloud_providers": ["AWS"],
        "compliance_frameworks": [],
        "data_types": [],
    }
    defaults.update(kwargs)
    org = MagicMock(spec=Organization)
    for k, v in defaults.items():
        setattr(org, k, v)
    return org


def _vendor(name: str, product: str = "") -> OrgVendor:
    v = MagicMock(spec=OrgVendor)
    v.vendor_name = name
    v.product_name = product
    return v


def _domain(name: str) -> OrgDomain:
    d = MagicMock(spec=OrgDomain)
    d.domain_name = name
    return d


async def _run(org, vendors=None, domains=None, upload_count=0):
    """Run validation with mocked DB fetch."""
    vendors = vendors or []
    domains = domains or []
    with patch(
        "app.services.assessment_validator._fetch_data",
        new=AsyncMock(return_value=(vendors, domains, upload_count)),
    ):
        session = AsyncMock()
        return await run_validation(org, session)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_required_fields():
    org = _org(name="", industry_label=None, primary_state=None, employee_range=None)
    result = await _run(org, vendors=[], domains=[])
    categories = {(i.field, i.severity) for i in result.issues}
    assert ("org_name", "error") in categories
    assert ("industry", "error") in categories
    assert ("primary_state", "error") in categories
    assert ("employee_range", "error") in categories
    assert ("vendors", "error") in categories
    assert ("domains", "error") in categories


@pytest.mark.asyncio
async def test_case_duplicate_vendors():
    vendors = [_vendor("Microsoft"), _vendor("microsoft")]
    result = await _run(_org(), vendors=vendors, domains=[_domain("example.com")])
    dupes = [i for i in result.issues if i.category == "duplicate" and i.field == "vendors"]
    assert dupes, "Expected a duplicate warning for case-variant vendor names"


@pytest.mark.asyncio
async def test_near_duplicate_vendors():
    vendors = [_vendor("Cisco"), _vendor("Ciscoo")]
    result = await _run(_org(), vendors=vendors, domains=[_domain("example.com")])
    near_dupes = [
        i for i in result.issues
        if i.category == "duplicate" and "similar" in i.message.lower()
    ]
    assert near_dupes, "Expected a near-duplicate warning for 'Cisco' and 'Ciscoo'"


@pytest.mark.asyncio
async def test_no_near_duplicate_for_unrelated():
    vendors = [_vendor("Cisco"), _vendor("Oracle")]
    result = await _run(_org(), vendors=vendors, domains=[_domain("example.com")])
    near_dupes = [
        i for i in result.issues
        if i.category == "duplicate" and "similar" in i.message.lower()
    ]
    assert not near_dupes, "Unrelated vendor names should not trigger near-duplicate warning"


@pytest.mark.asyncio
async def test_domain_format_invalid():
    domains = [_domain("not_a_domain")]
    result = await _run(_org(), vendors=[_vendor("Cisco")], domains=domains)
    fmt_errs = [i for i in result.issues if i.category == "invalid_format" and i.field == "domains"]
    assert fmt_errs, "Expected invalid_format error for malformed domain"


@pytest.mark.asyncio
async def test_hipaa_without_health_data():
    org = _org(compliance_frameworks=["HIPAA"], data_types=["PII (names, SSNs)"])
    result = await _run(org, vendors=[_vendor("Epic")], domains=[_domain("clinic.com")])
    conflicts = [i for i in result.issues if i.category == "conflict" and "HIPAA" in i.message]
    assert conflicts, "Expected conflict warning for HIPAA without health data type"


@pytest.mark.asyncio
async def test_pci_without_payment_data():
    org = _org(compliance_frameworks=["PCI-DSS"], data_types=["PII (names, SSNs)"])
    result = await _run(org, vendors=[_vendor("Stripe")], domains=[_domain("shop.com")])
    conflicts = [i for i in result.issues if i.category == "conflict" and "PCI-DSS" in i.message]
    assert conflicts, "Expected conflict warning for PCI-DSS without payment data type"


@pytest.mark.asyncio
async def test_no_conflict_when_data_type_matches():
    org = _org(compliance_frameworks=["HIPAA"], data_types=["PHI (health records)"])
    result = await _run(org, vendors=[_vendor("Epic")], domains=[_domain("clinic.com")])
    conflicts = [i for i in result.issues if i.category == "conflict" and "HIPAA" in i.message]
    assert not conflicts


@pytest.mark.asyncio
async def test_all_unsure_controls():
    org = _org(security_controls={"mfa_enabled": "unsure", "firewall_in_place": "unsure"})
    result = await _run(org, vendors=[_vendor("Cisco")], domains=[_domain("example.com")])
    quality = [i for i in result.issues if i.category == "quality" and i.field == "security_controls"]
    assert quality, "Expected quality warning when all controls are 'unsure'"


@pytest.mark.asyncio
async def test_score_calculation():
    org = _org(name="", industry_label=None, primary_state=None, employee_range=None)
    result = await _run(org, vendors=[], domains=[])
    errors = [i for i in result.issues if i.severity == "error"]
    warnings = [i for i in result.issues if i.severity == "warning"]
    infos = [i for i in result.issues if i.severity == "info"]
    expected = max(
        0.0,
        100.0 - len(errors) * 15 - len(warnings) * 5 - len(infos) * 1,
    )
    assert result.score == expected


@pytest.mark.asyncio
async def test_passed_with_warnings_only():
    # Revenue range missing → warning; no errors
    org = _org(revenue_range=None)
    result = await _run(org, vendors=[_vendor("Cisco")], domains=[_domain("example.com")])
    assert result.passed is True
    warnings = [i for i in result.issues if i.severity == "warning"]
    assert warnings  # at least the revenue_range warning


@pytest.mark.asyncio
async def test_fully_complete_org():
    org = _org(
        compliance_frameworks=["HIPAA"],
        data_types=["PHI (health records)"],
        security_controls={"mfa_enabled": "yes", "firewall_in_place": "yes"},
    )
    result = await _run(
        org,
        vendors=[_vendor("Epic"), _vendor("Cisco")],
        domains=[_domain("clinic.com")],
        upload_count=2,
    )
    errors = [i for i in result.issues if i.severity == "error"]
    assert not errors
    assert result.passed is True
