"""Vulnerability routes — v1."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.repositories.exploited_vuln import (
    JsonExploitedVulnRepository,
    SqlExploitedVulnRepository,
    get_exploited_repo,
)
from app.schemas.vulnerability import (
    ALLOWED_SORT_FIELDS,
    ExploitedVulnListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/exploited", response_model=ExploitedVulnListResponse)
async def list_exploited_vulnerabilities(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, alias="page_size", description="Items per page (max 100)")
    ] = 25,
    sort_by: Annotated[
        str,
        Query(alias="sort_by", description=f"Sort field. Allowed: {sorted(ALLOWED_SORT_FIELDS)}"),
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

    Paginated, sortable, and filterable.  In demo mode the data comes from a
    local JSON fixture; set ``ENABLE_DEMO_MODE=False`` to query the database
    instead.
    """
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. "
                f"Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
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

    return ExploitedVulnListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
