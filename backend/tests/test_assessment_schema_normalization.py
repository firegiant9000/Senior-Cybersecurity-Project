"""Unit tests for assessment-related schema normalization and boundaries."""

import pytest
from pydantic import ValidationError

from app.schemas.assessment_submission import AssessmentSubmissionCreate, AssessmentSubmissionUpdate
from app.schemas.org_domain import OrgDomainCreate
from app.schemas.org_vendor import OrgVendorCreate, OrgVendorUpdate


def _valid_assessment_data() -> dict:
    return {
        "company_profile": {
            "primary_contact_name": "Jane Doe",
            "primary_contact_email": "jane@example.com",
            "employee_count": 45,
            "annual_revenue_usd": 1250000,
            "critical_assets": ["Customer Portal"],
        },
        "security_controls": {
            "mfa_enabled": True,
            "endpoint_protection": True,
            "backup_strategy": "Daily encrypted offsite backups",
            "incident_response_plan": False,
        },
        "risk_assessment": {
            "top_risks": ["Phishing"],
            "compliance_requirements": ["SOC2"],
            "notes": "Need tabletop exercise.",
        },
    }


def test_assessment_create_rejects_invalid_nested_type():
    payload = {
        "organization_id": 1,
        "status": "Draft",
        "data": _valid_assessment_data(),
    }
    payload["data"]["company_profile"]["employee_count"] = "not-an-int"
    with pytest.raises(ValidationError):
        AssessmentSubmissionCreate(**payload)


def test_assessment_update_rejects_negative_revenue():
    payload = {
        "status": "Draft",
        "data": _valid_assessment_data(),
    }
    payload["data"]["company_profile"]["annual_revenue_usd"] = -1
    with pytest.raises(ValidationError):
        AssessmentSubmissionUpdate(**payload)


def test_vendor_create_normalizes_whitespace():
    model = OrgVendorCreate(vendor_name="  Microsoft   Corp  ", product_name="  Office  365 ")
    assert model.vendor_name == "Microsoft Corp"
    assert model.product_name == "Office 365"


def test_vendor_update_normalizes_optional_fields():
    model = OrgVendorUpdate(vendor_name="  Cisco   ", product_name="  SecureX   Agent ")
    assert model.vendor_name == "Cisco"
    assert model.product_name == "SecureX Agent"


def test_domain_create_normalizes_case_and_trailing_dot():
    model = OrgDomainCreate(domain_name="  Example.COM. ")
    assert model.domain_name == "example.com"


def test_domain_create_rejects_invalid_domain():
    with pytest.raises(ValidationError):
        OrgDomainCreate(domain_name="not a domain")
