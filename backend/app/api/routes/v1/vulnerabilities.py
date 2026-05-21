"""Vulnerability routes — v1."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.limiter import limiter
from app.repositories.exploited_vuln import (
    JsonExploitedVulnRepository,
    SqlExploitedVulnRepository,
    get_exploited_repo,
)
from app.schemas.vulnerability import (
    ALLOWED_SORT_FIELDS,
    ExploitedVulnListResponse,
    RiskScoreStatsResponse,
    SeveritySummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/exploited", response_model=ExploitedVulnListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_exploited_vulnerabilities(
    request: Request,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, alias="page_size", description="Items per page (max 100)")
    ] = 25,
    sort_by: Annotated[
        str,
        Query(
            alias="sort_by",
            description=f"Sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
        ),
    ] = "kev_date_added",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "desc",
    search: Annotated[str | None, Query(description="Search CVE IDs (partial match)")] = None,
    severity: Annotated[
        str | None,
        Query(description="Filter by severity: Critical, High, Medium, Low, Unknown"),
    ] = None,
    repo: JsonExploitedVulnRepository | SqlExploitedVulnRepository = Depends(get_exploited_repo),
) -> ExploitedVulnListResponse:
    """List exploited vulnerabilities from the CISA KEV catalog.

    Paginated, sortable, and filterable. When the caller's organisation has
    ``is_demo=True`` the data is served from a curated JSON fixture; all
    other callers hit the live database.
    """
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_exploited(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            severity=severity,
        )
    except FileNotFoundError as exc:
        logger.error("Fixture file missing: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        logger.error("Repository not implemented: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error in exploited vulnerabilities route: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unhandled error in exploited vulnerabilities route: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Verify DATABASE_URL and PostgreSQL credentials.",
        ) from exc

    return ExploitedVulnListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/exploited/severity-summary", response_model=SeveritySummaryResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def exploited_severity_summary(
    request: Request,
    search: Annotated[str | None, Query(description="Search CVE IDs (partial match)")] = None,
    severity: Annotated[
        str | None,
        Query(description="Filter by severity: Critical, High, Medium, Low, Unknown"),
    ] = None,
    repo: JsonExploitedVulnRepository | SqlExploitedVulnRepository = Depends(get_exploited_repo),
) -> SeveritySummaryResponse:
    """Return severity label counts for the full KEV dataset (no pagination)."""
    try:
        return await repo.severity_summary(search=search, severity=severity)
    except FileNotFoundError as exc:
        logger.error("Fixture file missing: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        logger.error("Repository not implemented: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error in severity summary: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unhandled error in severity summary: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable.") from exc


@router.get("/risk-scored/stats", response_model=RiskScoreStatsResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def get_risk_score_stats(
    request: Request,
    data_source: Annotated[
        Literal["all", "kev", "nvd"],
        Query(
            alias="data_source",
            description="Filter by source: all, kev, or nvd",
        ),
    ] = "all",
    repo: JsonExploitedVulnRepository | SqlExploitedVulnRepository = Depends(get_exploited_repo),
) -> RiskScoreStatsResponse:
    """Return full-dataset risk score distribution stats (not paginated)."""
    try:
        return await repo.risk_score_stats(data_source=data_source)
    except SQLAlchemyError as exc:
        logger.error("Database error in risk-score stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/risk-scored", response_model=ExploitedVulnListResponse)
@limiter.limit(settings.RATE_LIMIT_DATA)
async def list_risk_scored_vulnerabilities(
    request: Request,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, alias="page_size", description="Items per page (max 100)")
    ] = 25,
    sort_by: Annotated[
        str,
        Query(
            alias="sort_by",
            description=f"Sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
        ),
    ] = "nvd_published",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "desc",
    data_source: Annotated[
        Literal["all", "kev", "nvd"],
        Query(
            alias="data_source",
            description="Filter by source: all, kev, or nvd",
        ),
    ] = "all",
    search: Annotated[
        str | None, Query(description="Search CVE IDs or descriptions (partial match)")
    ] = None,
    repo: JsonExploitedVulnRepository | SqlExploitedVulnRepository = Depends(get_exploited_repo),
) -> ExploitedVulnListResponse:
    """List risk-scored vulnerabilities using NVD CVSS + KEV exploitation context."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        items, total = await repo.list_risk_scored(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            data_source=data_source,
            search=search,
        )
    except FileNotFoundError as exc:
        logger.error("Fixture file missing: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        logger.error("Repository not implemented: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error in risk-scored vulnerabilities route: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unhandled error in risk-scored vulnerabilities route: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Verify DATABASE_URL and PostgreSQL credentials.",
        ) from exc

    return ExploitedVulnListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
