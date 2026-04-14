"""Shared enumerations for Organization and related models."""

from enum import StrEnum


class IndustryLabel(StrEnum):
    """Friendly industry labels shown in the onboarding wizard."""

    FINANCE_INSURANCE = "Finance & Insurance"
    HEALTHCARE = "Healthcare"
    TECH_SOFTWARE = "Tech & Software"
    GOVERNMENT = "Government"
    RETAIL_ECOMMERCE = "Retail & E-Commerce"
    EDUCATION = "Education"
    MANUFACTURING = "Manufacturing"
    PROFESSIONAL_SERVICES = "Professional Services"
    OTHER = "Other"


# Maps each friendly industry label to its underlying IC3 sector.
INDUSTRY_TO_IC3_SECTOR: dict[IndustryLabel, "IC3Sector"] = {}  # populated after IC3Sector


class IC3Sector(StrEnum):
    FINANCE = "Finance"
    HEALTHCARE = "Healthcare"
    TECHNOLOGY = "Technology"
    GOVERNMENT = "Government"
    RETAIL = "Retail"
    EDUCATION = "Education"
    MANUFACTURING = "Manufacturing"
    REAL_ESTATE = "Real Estate"
    CONSTRUCTION = "Construction"
    PROFESSIONAL_SERVICES = "Professional Services"
    LEGAL_SERVICES = "Legal Services"
    TRANSPORTATION = "Transportation"
    HOSPITALITY = "Hospitality"
    NON_PROFIT = "Non-Profit"


INDUSTRY_TO_IC3_SECTOR.update(
    {
        IndustryLabel.FINANCE_INSURANCE: IC3Sector.FINANCE,
        IndustryLabel.HEALTHCARE: IC3Sector.HEALTHCARE,
        IndustryLabel.TECH_SOFTWARE: IC3Sector.TECHNOLOGY,
        IndustryLabel.GOVERNMENT: IC3Sector.GOVERNMENT,
        IndustryLabel.RETAIL_ECOMMERCE: IC3Sector.RETAIL,
        IndustryLabel.EDUCATION: IC3Sector.EDUCATION,
        IndustryLabel.MANUFACTURING: IC3Sector.MANUFACTURING,
        IndustryLabel.PROFESSIONAL_SERVICES: IC3Sector.PROFESSIONAL_SERVICES,
        IndustryLabel.OTHER: IC3Sector.TECHNOLOGY,  # sensible default
    }
)


class EmployeeRange(StrEnum):
    SOLO = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-500"
    ENTERPRISE = "501-1000"
    LARGE_ENTERPRISE = "1001+"


class RevenueRange(StrEnum):
    UNDER_1M = "Under $1M"
    FROM_1M_5M = "$1M-$5M"
    FROM_5M_10M = "$5M-$10M"
    FROM_10M_50M = "$10M-$50M"
    FROM_50M_100M = "$50M-$100M"
    OVER_100M = "$100M+"


class OrgRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"


class InviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"
