"""Economics routes — v1."""
# pylint: disable=duplicate-code

import logging
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.economics import (
    ALLOWED_SORT_FIELDS,
    EconomicIndicatorItem,
    EconomicIndicatorListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# BEA Regional API for state-level economic data
BEA_API_URL = "https://apps.bea.gov/api/data"
BEA_DATASET = "Regional"
BEA_TABLE = "CAGDP2"  # County GDP (provides state-level aggregates)
BEA_LINECODE = "1"  # GDP: All industry total

# Census County Business Patterns API for state-level establishment counts
CBP_API_URL = "https://api.census.gov/data/2022/cbp"

# State FIPS codes (format: XXXXX where last 3 digits = 000 for state level)
STATE_FIPS_CODES = {
    "01000": "Alabama",
    "02000": "Alaska",
    "04000": "Arizona",
    "05000": "Arkansas",
    "06000": "California",
    "08000": "Colorado",
    "09000": "Connecticut",
    "10000": "Delaware",
    "12000": "Florida",
    "13000": "Georgia",
    "15000": "Hawaii",
    "16000": "Idaho",
    "17000": "Illinois",
    "18000": "Indiana",
    "19000": "Iowa",
    "20000": "Kansas",
    "21000": "Kentucky",
    "22000": "Louisiana",
    "23000": "Maine",
    "24000": "Maryland",
    "25000": "Massachusetts",
    "26000": "Michigan",
    "27000": "Minnesota",
    "28000": "Mississippi",
    "29000": "Missouri",
    "30000": "Montana",
    "31000": "Nebraska",
    "32000": "Nevada",
    "33000": "New Hampshire",
    "34000": "New Jersey",
    "35000": "New Mexico",
    "36000": "New York",
    "37000": "North Carolina",
    "38000": "North Dakota",
    "39000": "Ohio",
    "40000": "Oklahoma",
    "41000": "Oregon",
    "42000": "Pennsylvania",
    "44000": "Rhode Island",
    "45000": "South Carolina",
    "46000": "South Dakota",
    "47000": "Tennessee",
    "48000": "Texas",
    "49000": "Utah",
    "50000": "Vermont",
    "51000": "Virginia",
    "53000": "Washington",
    "54000": "West Virginia",
    "55000": "Wisconsin",
    "56000": "Wyoming",
}

# In-memory cache for BEA data (avoids re-querying all 50 states)
_BEA_CACHE: list[dict[str, float | int | str]] | None = None
_BEA_CACHE_LOADED = False


async def _load_census_establishment_counts(
    client: httpx.AsyncClient,
) -> dict[str, int]:
    """Return state -> establishment count from Census CBP.

    Uses NAICS 00 (all sectors) at state level.
    """
    params: dict[str, str] = {
        "get": "ESTAB,NAME,NAICS2017",
        "for": "state:*",
        "NAICS2017": "00",
    }
    if settings.CENSUS_API_KEY:
        params["key"] = settings.CENSUS_API_KEY

    response = await client.get(CBP_API_URL, params=params)
    response.raise_for_status()
    raw_rows = response.json()

    # Header row followed by rows: [ESTAB, NAME, NAICS2017, state]
    rows = raw_rows[1:] if isinstance(raw_rows, list) else []
    establishments_by_state: dict[str, int] = {}
    for row in rows:
        try:
            estab = int(row[0])
            state_name = str(row[1]).strip()
        except (ValueError, TypeError, IndexError):
            continue
        establishments_by_state[state_name] = estab

    return establishments_by_state


async def _load_bea_cache():
    """Load and cache all 50 state economic data from BEA API once."""
    global _BEA_CACHE, _BEA_CACHE_LOADED

    if _BEA_CACHE_LOADED and _BEA_CACHE is not None:
        return _BEA_CACHE

    items: list[dict[str, float | int | str]] = []

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            establishments_by_state = await _load_census_establishment_counts(client)

            for fips_code, state_name in STATE_FIPS_CODES.items():
                response = await client.get(
                    BEA_API_URL,
                    params={
                        "UserID": settings.BEA_API_KEY,
                        "Method": "GetData",
                        "DatasetName": BEA_DATASET,
                        "TableName": BEA_TABLE,
                        "LineCode": BEA_LINECODE,
                        "GeoFips": fips_code,
                        "Year": "2023",
                        "ResultFormat": "JSON",
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Extract GDP value from BEA response
                gdp_billions = None
                if "BEAAPI" in data and "Results" in data["BEAAPI"]:
                    results = data["BEAAPI"]["Results"]
                    if "Data" in results and results["Data"]:
                        record = results["Data"][0]
                        gdp_value = record.get("DataValue", "0")
                        unit_mult = record.get("UNIT_MULT", 0)

                        try:
                            # BEA CAGDP2 reports CL_UNIT="Thousands of dollars".
                            # DataValue may include commas and UNIT_MULT scaling.
                            raw_value = str(gdp_value).replace(",", "")
                            gdp_val = float(raw_value) if raw_value and raw_value != "NA" else 0
                            unit_multiplier = 10 ** int(unit_mult) if unit_mult else 1
                            gdp_dollars = gdp_val * unit_multiplier * 1_000
                            gdp_billions = gdp_dollars / 1_000_000_000
                        except (ValueError, TypeError):
                            gdp_billions = 0

                if gdp_billions and gdp_billions > 0:
                    # Use real state establishment counts from Census CBP.
                    smb_count = establishments_by_state.get(state_name, 0)
                    if smb_count <= 0:
                        logger.warning("Missing Census establishment count for %s", state_name)
                        continue

                    # Approximate per-establishment revenue from BEA state GDP.
                    avg_revenue = (gdp_billions * 1_000_000_000) / smb_count

                    items.append(
                        {
                            "id": len(items) + 1,
                            "state": state_name,
                            "smb_count": smb_count,
                            "avg_revenue": avg_revenue,
                        }
                    )
                    logger.debug("BEA Cache: %s - GDP $%.1fB", state_name, gdp_billions)

        _BEA_CACHE = items
        _BEA_CACHE_LOADED = True
        logger.info("BEA cache loaded: %s states", len(items))
        return items

    except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
        logger.error("Failed to load BEA cache: %s", e)
        _BEA_CACHE_LOADED = True
        _BEA_CACHE = []
        return []


@router.get("/indicators", response_model=EconomicIndicatorListResponse)
async def list_economic_indicators(
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
    ] = "state",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(alias="sort_order", description="Sort direction")
    ] = "asc",
    search: Annotated[str | None, Query(description="Search state name (partial match)")] = None,
) -> EconomicIndicatorListResponse:
    """Fetch real economic indicators from BEA Regional Economic Accounts.

    Data source: Bureau of Economic Analysis (BEA) Regional Accounts
    Table: CAGDP2 - Gross Domestic Product (GDP) by County (aggregated to state level)
    Metric: GDP in thousands of dollars, all industry total

    Used for state-level economic impact modeling of cybersecurity threats.
    Cached on first load for fast pagination.
    """
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by value {sort_by!r}. Allowed values: {sorted(ALLOWED_SORT_FIELDS)}"
            ),
        )

    try:
        # Load cached BEA data (queries all 50 states only on first request)
        items = await _load_bea_cache()

        if not items:
            raise HTTPException(status_code=502, detail="Failed to load economic data from BEA")

        # Apply state search filter
        if search:
            needle = search.lower()
            items = [i for i in items if needle in str(i.get("state", "")).lower()]

        # Sort the data
        reverse = sort_order == "desc"
        sorted_items = sorted(items, key=lambda x: x.get(sort_by, 0), reverse=reverse)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = sorted_items[start:end]
        response_items = [EconomicIndicatorItem.model_validate(item) for item in paginated_items]

        return EconomicIndicatorListResponse(
            total=len(sorted_items),
            page=page,
            page_size=page_size,
            items=response_items,
        )
    except httpx.HTTPError as e:
        logger.error("BEA API HTTP error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"BEA API error: {str(e)}",
        ) from e
    except ValueError as e:
        logger.error("BEA API JSON parsing error: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Failed to parse BEA API response",
        ) from e
    except (TypeError, KeyError) as e:
        logger.error("Unexpected error fetching BEA data: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e
