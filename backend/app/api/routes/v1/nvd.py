"""NVD routes — v1."""
# pylint: disable=duplicate-code,line-too-long

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.repositories.nvd import NvdRepository, get_nvd_repo
from app.schemas.nvd import ALLOWED_SORT_FIELDS, NvdCveListResponse
from app.schemas.nvd_analytics import SeverityDistributionResponse
from app.services.nvd_analytics import NVDAnalytics

logger = logging.getLogger(__name__)

router = APIRouter()

NVD_API_KEY = "647c0a71-2445-4de5-aa4f-5b808894c755"
NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Demo NVD CVE data (fallback if API fails)
DEMO_NVD_DATA = [
    {"id": "CVE-2024-46805", "description": "Remote Code Execution in OpenSSH before 9.8", "severity_score": 9.8, "severity_label": "Critical", "published_date": "2024-11-25", "last_modified": "2024-12-01"},
    {"id": "CVE-2024-50633", "description": "Buffer Overflow in Linux kernel netfilter module", "severity_score": 8.6, "severity_label": "High", "published_date": "2024-12-10", "last_modified": "2024-12-11"},
    {"id": "CVE-2024-45490", "description": "SQL Injection in Laravel framework", "severity_score": 8.9, "severity_label": "Critical", "published_date": "2024-11-18", "last_modified": "2024-11-20"},
    {"id": "CVE-2024-47396", "description": "Privilege Escalation in Windows Print Spooler", "severity_score": 7.8, "severity_label": "High", "published_date": "2024-11-30", "last_modified": "2024-12-02"},
    {"id": "CVE-2024-48999", "description": "Cross-Site Scripting in WordPress WooCommerce plugin", "severity_score": 6.1, "severity_label": "Medium", "published_date": "2024-12-05", "last_modified": "2024-12-06"},
    {"id": "CVE-2024-49283", "description": "Authentication Bypass in Apache Struts 2", "severity_score": 9.1, "severity_label": "Critical", "published_date": "2024-12-08", "last_modified": "2024-12-09"},
    {"id": "CVE-2024-48891", "description": "Denial of Service in Nginx HTTP/2 implementation", "severity_score": 7.5, "severity_label": "High", "published_date": "2024-12-02", "last_modified": "2024-12-03"},
    {"id": "CVE-2024-47234", "description": "File Disclosure in PHP file inclusion vulnerability", "severity_score": 6.5, "severity_label": "Medium", "published_date": "2024-11-27", "last_modified": "2024-11-29"},
    {"id": "CVE-2024-46102", "description": "Remote Code Execution in ImageMagick", "severity_score": 8.8, "severity_label": "High", "published_date": "2024-11-20", "last_modified": "2024-11-22"},
    {"id": "CVE-2024-45678", "description": "Insecure Deserialization in Java libraries", "severity_score": 8.1, "severity_label": "High", "published_date": "2024-11-15", "last_modified": "2024-11-17"},
    {"id": "CVE-2024-50234", "description": "Path Traversal in Express.js middleware", "severity_score": 7.3, "severity_label": "High", "published_date": "2024-12-09", "last_modified": "2024-12-10"},
    {"id": "CVE-2024-49876", "description": "Integer Overflow in Chrome V8 JavaScript engine", "severity_score": 8.3, "severity_label": "High", "published_date": "2024-12-06", "last_modified": "2024-12-07"},
    {"id": "CVE-2024-48567", "description": "Use-after-free in Firefox browser", "severity_score": 7.9, "severity_label": "High", "published_date": "2024-12-03", "last_modified": "2024-12-04"},
    {"id": "CVE-2024-47123", "description": "Command Injection in Node.js child_process module", "severity_score": 8.4, "severity_label": "High", "published_date": "2024-11-25", "last_modified": "2024-11-26"},
    {"id": "CVE-2024-46891", "description": "LDAP Injection in Active Directory", "severity_score": 7.2, "severity_label": "High", "published_date": "2024-11-22", "last_modified": "2024-11-24"},
    {"id": "CVE-2024-50111", "description": "Race Condition in MySQL database engine", "severity_score": 6.9, "severity_label": "Medium", "published_date": "2024-12-11", "last_modified": "2024-12-12"},
    {"id": "CVE-2024-49345", "description": "XXE Attack in XML parsers", "severity_score": 7.6, "severity_label": "High", "published_date": "2024-12-07", "last_modified": "2024-12-08"},
    {"id": "CVE-2024-48234", "description": "CORS Misconfiguration in Flask applications", "severity_score": 6.3, "severity_label": "Medium", "published_date": "2024-12-04", "last_modified": "2024-12-05"},
    {"id": "CVE-2024-47001", "description": "Weak Cryptography in OpenSSL", "severity_score": 7.4, "severity_label": "High", "published_date": "2024-11-28", "last_modified": "2024-11-30"},
    {"id": "CVE-2024-45999", "description": "Memory Leak in Python libraries", "severity_score": 6.2, "severity_label": "Medium", "published_date": "2024-11-19", "last_modified": "2024-11-21"},
]


@router.get("/cves", response_model=NvdCveListResponse)
async def list_nvd_cves(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=200, alias="page_size", description="Items per page (max 200)")
    ] = 50,
    sort_by: Annotated[
        str,
        Query(
            alias="sort_by",
            description=f"Sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
        ),
    ] = "published_date",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "desc",
    *,
    repo: Annotated[NvdRepository, Depends(get_nvd_repo)],
) -> NvdCveListResponse:
    """Fetch NVD CVEs from the local database (populated by ingestion)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_cves(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return NvdCveListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    except ValueError as e:
        logger.error("NVD query validation error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (TypeError, KeyError) as e:
        logger.error("Unexpected error in NVD route: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/analytics/severity-distribution",
    response_model=SeverityDistributionResponse,
)
async def get_severity_distribution(
    date_from: Annotated[date | None, Query(description="Filter: start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[date | None, Query(description="Filter: end date (YYYY-MM-DD)")] = None,
    db: AsyncSession = Depends(get_session),
) -> SeverityDistributionResponse:
    """Get CVE counts grouped by severity level."""
    analytics = NVDAnalytics(db)
    items = await analytics.get_severity_distribution(
        date_from=date_from,
        date_to=date_to,
    )
    total = sum(item["count"] for item in items)
    return SeverityDistributionResponse(
        items=items,
        total_cves=total,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
