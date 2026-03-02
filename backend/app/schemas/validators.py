"""Data validation and normalization utilities for all ingested data sources.

This module provides:
- Pydantic validators for input data consistency
- Normalization functions for standardizing formats
- Range/bounds checking for all numeric fields
"""

import re
from datetime import date
from typing import Any

from pydantic import (  # type: ignore[import-not-found]  # pylint: disable=import-error
    BaseModel,
    Field,
    field_validator,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Common Validators (used across multiple data sources)
# ═══════════════════════════════════════════════════════════════════════════════


def validate_cvss_score(score: float | None) -> float | None:
    """Validate CVSS score is in [0.0, 10.0] range.

    Args:
        score: Raw CVSS score or None

    Returns:
        Clamped score in [0.0, 10.0], or None if input is None/invalid

    Raises:
        ValueError: If score is not numeric or out of range (before clamping)
    """
    if score is None:
        return None
    try:
        score_float = float(score)
        if score_float < 0.0 or score_float > 10.0:
            raise ValueError(f"CVSS score {score_float} out of [0.0, 10.0] range")
        return score_float
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid CVSS score: {score}") from e


def normalize_cvss_score(score: float | None) -> float | None:
    """Normalize CVSS score: clamp to [0.0, 10.0], return None if invalid.

    Unlike validate_cvss_score, this doesn't raise errors.

    Args:
        score: Raw CVSS score or None

    Returns:
        Clamped score in [0.0, 10.0], or None if invalid
    """
    if score is None:
        return None
    try:
        score_float = float(score)
        return max(0.0, min(score_float, 10.0))
    except (TypeError, ValueError):
        return None


def validate_iso_date(date_str: str | None) -> str | None:
    """Validate ISO YYYY-MM-DD date string.

    Args:
        date_str: Date string in ISO format or None

    Returns:
        Normalized ISO date string or None

    Raises:
        ValueError: If date string is invalid format
    """
    if date_str is None or date_str == "":
        return None
    try:
        parsed = date.fromisoformat(date_str)
        return parsed.isoformat()
    except ValueError as e:
        raise ValueError(f"Invalid ISO date: {date_str}") from e


def normalize_iso_date(date_str: str | None) -> str | None:
    """Normalize ISO date string. Returns None if invalid.

    Unlike validate_iso_date, doesn't raise errors.

    Args:
        date_str: Date string in ISO format or None

    Returns:
        Normalized ISO date string or None (if invalid)
    """
    if date_str is None or date_str == "":
        return None
    try:
        parsed = date.fromisoformat(date_str)
        return parsed.isoformat()
    except ValueError:
        return None


def validate_state_code(state: str) -> str:
    """Validate US state code (2-letter uppercase).

    Args:
        state: State code string

    Returns:
        Uppercase 2-letter state code

    Raises:
        ValueError: If not a valid 2-letter code
    """
    if not isinstance(state, str) or len(state) != 2:
        raise ValueError(f"Invalid state code: {state} (must be 2 letters)")
    return state.upper()


def normalize_state_code(state: str) -> str | None:
    """Normalize state code to uppercase. Returns None if invalid."""
    if not isinstance(state, str):
        return None
    state_upper = state.upper().strip()
    if len(state_upper) == 2:
        return state_upper
    return None


def validate_cve_id(cve_id: str) -> str:
    """Validate CVE ID format (CVE-YYYY-NNNNN).

    Args:
        cve_id: CVE identifier string

    Returns:
        Uppercase CVE ID

    Raises:
        ValueError: If invalid CVE format
    """
    if not isinstance(cve_id, str):
        raise ValueError(f"CVE ID must be string, got {type(cve_id)}")
    cve_upper = cve_id.upper().strip()
    pattern = r"^CVE-\d{4}-\d{4,}$"
    if not re.match(pattern, cve_upper):
        raise ValueError(f"Invalid CVE ID format: {cve_id} (expected CVE-YYYY-NNNNN)")
    return cve_upper


def normalize_cve_id(cve_id: str) -> str | None:
    """Normalize CVE ID to uppercase. Returns None if invalid."""
    if not isinstance(cve_id, str):
        return None
    cve_upper = cve_id.upper().strip()
    pattern = r"^CVE-\d{4}-\d{4,}$"
    if re.match(pattern, cve_upper):
        return cve_upper
    return None


def validate_positive_float(value: float | None, min_val: float = 0.0) -> float | None:
    """Validate float is >= min_val.

    Args:
        value: Numeric value or None
        min_val: Minimum allowed value (default: 0.0)

    Returns:
        Validated float or None

    Raises:
        ValueError: If value is invalid or < min_val
    """
    if value is None:
        return None
    try:
        float_val = float(value)
        if float_val < min_val:
            raise ValueError(f"Value {float_val} is less than minimum {min_val}")
        return float_val
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid float value: {value}") from e


def normalize_positive_float(
    value: float | None, min_val: float = 0.0
) -> float | None:
    """Normalize float, clamping to min_val. Returns None if invalid."""
    if value is None:
        return None
    try:
        float_val = float(value)
        return max(min_val, float_val)
    except (TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# NVD CVE Validation Schema
# ═══════════════════════════════════════════════════════════════════════════════


class NvdCveValidationSchema(BaseModel):
    """Validation schema for NVD CVE records."""

    cve_id: str = Field(..., description="CVE identifier (e.g., CVE-2021-44228)")
    description: str = Field(
        ..., min_length=1, description="CVE description (required, non-empty)"
    )
    cvss_score: float | None = Field(
        default=None,
        description="CVSS v3.1 base score [0.0-10.0] or None",
        ge=0.0,
        le=10.0,
    )
    severity: str | None = Field(
        default=None,
        description="CVSS severity label (Critical, High, Medium, Low, Unknown, or None)",
    )
    published_date: str | None = Field(
        default=None, description="ISO YYYY-MM-DD publication date or None"
    )

    @field_validator("cve_id", mode="before")
    @classmethod
    def validate_cve_format(cls, v: Any) -> str:
        """Validate CVE ID format."""
        return validate_cve_id(str(v))

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, v: Any) -> str:
        """Ensure description is non-empty string."""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty")
        return v

    @field_validator("cvss_score", mode="before")
    @classmethod
    def validate_score(cls, v: Any) -> float | None:
        """Validate CVSS score is in [0.0, 10.0]."""
        return normalize_cvss_score(v)

    @field_validator("published_date", mode="before")
    @classmethod
    def validate_date(cls, v: Any) -> str | None:
        """Validate ISO date format."""
        return normalize_iso_date(str(v) if v else None)


# ═══════════════════════════════════════════════════════════════════════════════
# IC3 Incident Validation Schema
# ═══════════════════════════════════════════════════════════════════════════════


class IC3IncidentValidationSchema(BaseModel):
    """Validation schema for IC3 incident records."""

    year: int = Field(..., ge=2000, le=2100, description="Year [2000-2100]")
    sector: str = Field(..., min_length=1, description="Business sector (non-empty)")
    state: str = Field(..., min_length=2, max_length=2, description="US state code (2-letter)")
    loss_amount: float = Field(
        ..., ge=0.0, description="Financial loss amount in USD (>= 0)"
    )

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: Any) -> str:
        """Validate and normalize state code."""
        state_norm = normalize_state_code(str(v))
        if state_norm is None:
            raise ValueError(f"Invalid state code: {v}")
        return state_norm

    @field_validator("sector", mode="before")
    @classmethod
    def validate_sector(cls, v: Any) -> str:
        """Ensure sector is non-empty string."""
        sector = str(v).strip() if v else ""
        if not sector:
            raise ValueError("Sector cannot be empty")
        return sector

    @field_validator("loss_amount", mode="before")
    @classmethod
    def validate_loss(cls, v: Any) -> float:
        """Ensure loss amount is non-negative float."""
        try:
            loss = float(v)
            if loss < 0:
                raise ValueError(f"Loss amount cannot be negative: {loss}")
            return loss
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid loss amount: {v}") from e


# ═══════════════════════════════════════════════════════════════════════════════
# Economic Indicator Validation Schema
# ═══════════════════════════════════════════════════════════════════════════════


class EconomicIndicatorValidationSchema(BaseModel):
    """Validation schema for economic indicator records."""

    state: str = Field(..., min_length=2, max_length=2, description="US state code (2-letter)")
    smb_count: int = Field(..., ge=0, description="Number of small/medium businesses")
    avg_revenue: float = Field(
        ..., ge=0.0, description="Average revenue per business in USD"
    )

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: Any) -> str:
        """Validate and normalize state code."""
        state_norm = normalize_state_code(str(v))
        if state_norm is None:
            raise ValueError(f"Invalid state code: {v}")
        return state_norm

    @field_validator("smb_count", mode="before")
    @classmethod
    def validate_count(cls, v: Any) -> int:
        """Ensure SMB count is non-negative integer."""
        try:
            count = int(float(v))
            if count < 0:
                raise ValueError(f"SMB count cannot be negative: {count}")
            return count
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid SMB count: {v}") from e

    @field_validator("avg_revenue", mode="before")
    @classmethod
    def validate_revenue(cls, v: Any) -> float:
        """Ensure revenue is non-negative float."""
        try:
            revenue = float(v)
            if revenue < 0:
                raise ValueError(f"Revenue cannot be negative: {revenue}")
            return revenue
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid revenue: {v}") from e


# ═══════════════════════════════════════════════════════════════════════════════
# CISA KEV Validation Schema
# ═══════════════════════════════════════════════════════════════════════════════


class CisaKevValidationSchema(BaseModel):
    """Validation schema for CISA Known Exploited Vulnerabilities."""

    cve_id: str = Field(..., description="CVE identifier (e.g., CVE-2021-44228)")
    vendor: str = Field(..., min_length=1, description="Vendor name (non-empty)")
    product: str = Field(..., min_length=1, description="Product name (non-empty)")
    due_date: str | None = Field(
        default=None, description="Patch due date in ISO YYYY-MM-DD or None"
    )

    @field_validator("cve_id", mode="before")
    @classmethod
    def validate_cve(cls, v: Any) -> str:
        """Validate CVE ID format."""
        return validate_cve_id(str(v))

    @field_validator("vendor", mode="before")
    @classmethod
    def validate_vendor(cls, v: Any) -> str:
        """Ensure vendor is non-empty string."""
        vendor = str(v).strip() if v else ""
        if not vendor:
            raise ValueError("Vendor cannot be empty")
        return vendor

    @field_validator("product", mode="before")
    @classmethod
    def validate_product(cls, v: Any) -> str:
        """Ensure product is non-empty string."""
        product = str(v).strip() if v else ""
        if not product:
            raise ValueError("Product cannot be empty")
        return product

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_date(cls, v: Any) -> str | None:
        """Validate ISO date format."""
        return normalize_iso_date(str(v) if v else None)
