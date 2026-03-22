"""Tests for backend/app/schemas/validators.py – issue #33."""

import pytest
from pydantic import ValidationError

from app.schemas.validators import (
    CisaKevValidationSchema,
    EconomicIndicatorValidationSchema,
    IC3IncidentValidationSchema,
    NvdCveValidationSchema,
    normalize_cve_id,
    normalize_cvss_score,
    normalize_iso_date,
    normalize_positive_float,
    normalize_state_code,
    validate_cve_id,
    validate_cvss_score,
    validate_iso_date,
    validate_positive_float,
    validate_state_code,
)

# ---------------------------------------------------------------------------
# validate_cvss_score
# ---------------------------------------------------------------------------

class TestValidateCvssScore:
    def test_none(self):
        assert validate_cvss_score(None) is None

    def test_zero(self):
        assert validate_cvss_score(0.0) == pytest.approx(0.0)

    def test_ten(self):
        assert validate_cvss_score(10.0) == pytest.approx(10.0)

    def test_mid(self):
        assert validate_cvss_score(5.5) == pytest.approx(5.5)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            validate_cvss_score(-1.0)

    def test_above_ten_raises(self):
        with pytest.raises(ValueError):
            validate_cvss_score(10.1)

    def test_string_raises(self):
        with pytest.raises(ValueError):
            validate_cvss_score("abc")


# ---------------------------------------------------------------------------
# normalize_cvss_score
# ---------------------------------------------------------------------------

class TestNormalizeCvssScore:
    def test_none(self):
        assert normalize_cvss_score(None) is None

    def test_valid(self):
        assert normalize_cvss_score(7.5) == pytest.approx(7.5)

    def test_negative_clamped(self):
        assert normalize_cvss_score(-1.0) == pytest.approx(0.0)

    def test_above_ten_clamped(self):
        assert normalize_cvss_score(15.0) == pytest.approx(10.0)

    def test_string_returns_none(self):
        assert normalize_cvss_score("abc") is None


# ---------------------------------------------------------------------------
# validate_iso_date
# ---------------------------------------------------------------------------

class TestValidateIsoDate:
    def test_none(self):
        assert validate_iso_date(None) is None

    def test_empty(self):
        assert validate_iso_date("") is None

    def test_valid(self):
        assert validate_iso_date("2024-01-15") == "2024-01-15"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_iso_date("not-a-date")


# ---------------------------------------------------------------------------
# normalize_iso_date
# ---------------------------------------------------------------------------

class TestNormalizeIsoDate:
    def test_none(self):
        assert normalize_iso_date(None) is None

    def test_empty(self):
        assert normalize_iso_date("") is None

    def test_valid(self):
        assert normalize_iso_date("2024-01-15") == "2024-01-15"

    def test_invalid_returns_none(self):
        assert normalize_iso_date("not-a-date") is None


# ---------------------------------------------------------------------------
# validate_state_code
# ---------------------------------------------------------------------------

class TestValidateStateCode:
    def test_upper(self):
        assert validate_state_code("CA") == "CA"

    def test_lower_normalized(self):
        assert validate_state_code("ca") == "CA"

    def test_single_char_raises(self):
        with pytest.raises(ValueError):
            validate_state_code("A")

    def test_three_chars_raises(self):
        with pytest.raises(ValueError):
            validate_state_code("ABC")


# ---------------------------------------------------------------------------
# normalize_state_code
# ---------------------------------------------------------------------------

class TestNormalizeStateCode:
    def test_upper(self):
        assert normalize_state_code("CA") == "CA"

    def test_lower(self):
        assert normalize_state_code("ca") == "CA"

    def test_single_char_returns_none(self):
        assert normalize_state_code("A") is None

    def test_int_returns_none(self):
        assert normalize_state_code(123) is None


# ---------------------------------------------------------------------------
# validate_cve_id
# ---------------------------------------------------------------------------

class TestValidateCveId:
    def test_valid(self):
        assert validate_cve_id("CVE-2021-44228") == "CVE-2021-44228"

    def test_lowercase_normalized(self):
        assert validate_cve_id("cve-2021-44228") == "CVE-2021-44228"

    def test_bad_format_raises(self):
        with pytest.raises(ValueError):
            validate_cve_id("NOTACVE")

    def test_int_raises(self):
        with pytest.raises(ValueError):
            validate_cve_id(123)


# ---------------------------------------------------------------------------
# normalize_cve_id
# ---------------------------------------------------------------------------

class TestNormalizeCveId:
    def test_valid(self):
        assert normalize_cve_id("CVE-2021-44228") == "CVE-2021-44228"

    def test_bad_returns_none(self):
        assert normalize_cve_id("bad") is None

    def test_int_returns_none(self):
        assert normalize_cve_id(123) is None


# ---------------------------------------------------------------------------
# validate_positive_float
# ---------------------------------------------------------------------------

class TestValidatePositiveFloat:
    def test_none(self):
        assert validate_positive_float(None) is None

    def test_positive(self):
        assert validate_positive_float(5.0) == pytest.approx(5.0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            validate_positive_float(-1.0)

    def test_string_raises(self):
        with pytest.raises(ValueError):
            validate_positive_float("abc")


# ---------------------------------------------------------------------------
# normalize_positive_float
# ---------------------------------------------------------------------------

class TestNormalizePositiveFloat:
    def test_none(self):
        assert normalize_positive_float(None) is None

    def test_positive(self):
        assert normalize_positive_float(5.0) == pytest.approx(5.0)

    def test_negative_clamped(self):
        assert normalize_positive_float(-1.0) == pytest.approx(0.0)

    def test_string_returns_none(self):
        assert normalize_positive_float("abc") is None


# ---------------------------------------------------------------------------
# NvdCveValidationSchema
# ---------------------------------------------------------------------------

class TestNvdCveValidationSchema:
    def test_valid(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "description": "Log4Shell vulnerability",
            "cvss_score": 9.8,
            "published_date": "2021-12-10",
        }
        obj = NvdCveValidationSchema(**data)
        assert obj.cve_id == "CVE-2021-44228"

    def test_invalid_cve_id(self):
        data = {
            "cve_id": "NOTACVE",
            "description": "desc",
            "cvss_score": 5.0,
        }
        with pytest.raises(ValidationError):
            NvdCveValidationSchema(**data)

    def test_empty_description(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "description": "",
            "cvss_score": 5.0,
        }
        with pytest.raises(ValidationError):
            NvdCveValidationSchema(**data)

    def test_cvss_out_of_range_normalized(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "description": "desc",
            "cvss_score": 15.0,
        }
        obj = NvdCveValidationSchema(**data)
        assert obj.cvss_score == pytest.approx(10.0)

    def test_valid_date(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "description": "desc",
            "cvss_score": 7.0,
            "published_date": "2024-01-15",
        }
        obj = NvdCveValidationSchema(**data)
        assert obj.published_date == "2024-01-15"


# ---------------------------------------------------------------------------
# IC3IncidentValidationSchema
# ---------------------------------------------------------------------------

class TestIC3IncidentValidationSchema:
    def test_valid(self):
        data = {
            "year": 2023,
            "sector": "Finance",
            "state": "CA",
            "loss_amount": 50000.0,
        }
        obj = IC3IncidentValidationSchema(**data)
        assert obj.state == "CA"

    def test_year_out_of_range(self):
        data = {
            "year": 1999,
            "sector": "Finance",
            "state": "CA",
            "loss_amount": 50000.0,
        }
        with pytest.raises(ValidationError):
            IC3IncidentValidationSchema(**data)

    def test_negative_loss(self):
        data = {
            "year": 2023,
            "sector": "Finance",
            "state": "CA",
            "loss_amount": -1.0,
        }
        with pytest.raises(ValidationError):
            IC3IncidentValidationSchema(**data)

    def test_invalid_state(self):
        data = {
            "year": 2023,
            "sector": "Finance",
            "state": "XYZ",
            "loss_amount": 50000.0,
        }
        with pytest.raises(ValidationError):
            IC3IncidentValidationSchema(**data)


# ---------------------------------------------------------------------------
# EconomicIndicatorValidationSchema
# ---------------------------------------------------------------------------

class TestEconomicIndicatorValidationSchema:
    def test_valid(self):
        data = {
            "state": "TX",
            "smb_count": 100000,
            "avg_revenue": 1500000.0,
        }
        obj = EconomicIndicatorValidationSchema(**data)
        assert obj.state == "TX"

    def test_negative_smb_count(self):
        data = {
            "state": "TX",
            "smb_count": -5,
            "avg_revenue": 1500000.0,
        }
        with pytest.raises(ValidationError):
            EconomicIndicatorValidationSchema(**data)

    def test_invalid_state(self):
        data = {
            "state": "X",
            "smb_count": 100000,
            "avg_revenue": 1500000.0,
        }
        with pytest.raises(ValidationError):
            EconomicIndicatorValidationSchema(**data)


# ---------------------------------------------------------------------------
# CisaKevValidationSchema
# ---------------------------------------------------------------------------

class TestCisaKevValidationSchema:
    def test_valid(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "vendor": "Apache",
            "product": "Log4j",
            "due_date": "2022-01-04",
        }
        obj = CisaKevValidationSchema(**data)
        assert obj.cve_id == "CVE-2021-44228"

    def test_empty_vendor(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "vendor": "",
            "product": "Log4j",
        }
        with pytest.raises(ValidationError):
            CisaKevValidationSchema(**data)

    def test_invalid_cve_id(self):
        data = {
            "cve_id": "BADID",
            "vendor": "Apache",
            "product": "Log4j",
        }
        with pytest.raises(ValidationError):
            CisaKevValidationSchema(**data)

    def test_valid_due_date(self):
        data = {
            "cve_id": "CVE-2021-44228",
            "vendor": "Apache",
            "product": "Log4j",
            "due_date": "2022-01-04",
        }
        obj = CisaKevValidationSchema(**data)
        assert obj.due_date == "2022-01-04"
