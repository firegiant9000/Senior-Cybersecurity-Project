"""Economic indicator ingestion from Census Bureau API and CSV fallback.

Includes data validation and normalization to ensure consistency.
"""

import csv
import logging

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EconomicIndicator
from app.schemas.validators import EconomicIndicatorValidationSchema

logger = logging.getLogger(__name__)


async def _upsert_economic_indicator(
    db: AsyncSession,
    *,
    state: str,
    smb_count: int,
    avg_revenue: float,
) -> None:
    """Upsert a single economic indicator row by state code.

    This avoids duplicate rows when ingestion runs multiple times.
    """
    existing = (
        await db.execute(select(EconomicIndicator).where(EconomicIndicator.state == state).limit(1))
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            EconomicIndicator(
                state=state,
                smb_count=smb_count,
                avg_revenue=avg_revenue,
            )
        )
        return

    existing.smb_count = smb_count
    existing.avg_revenue = avg_revenue
    db.add(existing)


def _normalize_econ_indicator(
    state: str, smb_count: int, avg_revenue: float
) -> tuple[str, int, float] | None:
    """Normalize and validate economic indicator data.

    Args:
        state: US state code (2-letter)
        smb_count: Number of small/medium businesses
        avg_revenue: Average revenue per business in USD

    Returns:
        Tuple of (state, smb_count, avg_revenue) or None if validation fails

    Normalization rules:
    - State code is uppercased and validated as 2-letter code
    - SMB count is validated to be non-negative integer
    - Average revenue is validated to be non-negative float
    """
    try:
        validated = EconomicIndicatorValidationSchema(
            state=state,
            smb_count=smb_count,
            avg_revenue=avg_revenue,
        )
        return (validated.state, validated.smb_count, validated.avg_revenue)
    except ValidationError as e:
        logger.warning(
            "Economic indicator validation failed for %s: %s",
            state,
            e,
        )
        return None


async def ingest_region_economics_from_census(db: AsyncSession) -> None:  # noqa: C901
    """
    Ingest regional economic indicators from US Census Bureau API.

    Uses ACS (American Community Survey) 5-year estimates:
    - B19013: Median household income by state
    - B06011: Income per capita by state
    - NAICS sector data for business counts

    Applies validation and normalization to all records.
    """
    settings = get_settings()
    api_key = settings.CENSUS_API_KEY

    if not api_key:
        logger.warning(
            "CENSUS_API_KEY not set. Attempting unauthenticated Census API requests. "
            "If rate-limited, will fall back to CSV."
        )

    try:
        # Using 2023 data (most recent complete Census ACS 5-year estimates as of 2026)
        cbp_url = "https://api.census.gov/data/2023/cbp"
        income_url = "https://api.census.gov/data/2023/acs/acs5"

        states = {
            "AL": "01",
            "AK": "02",
            "AZ": "04",
            "AR": "05",
            "CA": "06",
            "CO": "08",
            "CT": "09",
            "DE": "10",
            "FL": "12",
            "GA": "13",
            "HI": "15",
            "ID": "16",
            "IL": "17",
            "IN": "18",
            "IA": "19",
            "KS": "20",
            "KY": "21",
            "LA": "22",
            "ME": "23",
            "MD": "24",
            "MA": "25",
            "MI": "26",
            "MN": "27",
            "MS": "28",
            "MO": "29",
            "MT": "30",
            "NE": "31",
            "NV": "32",
            "NH": "33",
            "NJ": "34",
            "NM": "35",
            "NY": "36",
            "NC": "37",
            "ND": "38",
            "OH": "39",
            "OK": "40",
            "OR": "41",
            "PA": "42",
            "RI": "44",
            "SC": "45",
            "SD": "46",
            "TN": "47",
            "TX": "48",
            "UT": "49",
            "VT": "50",
            "VA": "51",
            "WA": "53",
            "WV": "54",
            "WI": "55",
            "WY": "56",
        }

        indicators_added = 0
        indicators_validated = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            cbp_params = {
                "get": "ESTAB,NAME",
                "for": "state:*",
                "EMPSZES": "001",  # all establishments
            }
            if api_key:
                cbp_params["key"] = api_key

            income_params = {
                "get": "B19013_001E,NAME",
                "for": "state:*",
            }
            if api_key:
                income_params["key"] = api_key

            cbp_resp = await client.get(cbp_url, params=cbp_params)
            cbp_resp.raise_for_status()
            cbp_data = cbp_resp.json()

            income_resp = await client.get(income_url, params=income_params)
            income_resp.raise_for_status()
            income_data = income_resp.json()

            smb_by_fips: dict[str, int] = {}
            for row in cbp_data[1:] if isinstance(cbp_data, list) else []:
                try:
                    estab_raw = str(row[0]).replace(",", "").strip()
                    fips = str(row[-1]).zfill(2)
                    smb_by_fips[fips] = int(estab_raw) if estab_raw.lower() != "null" else 0
                except (TypeError, ValueError, IndexError):
                    continue

            income_by_fips: dict[str, float] = {}
            for row in income_data[1:] if isinstance(income_data, list) else []:
                try:
                    income_raw = str(row[0]).replace(",", "").strip()
                    fips = str(row[-1]).zfill(2)
                    income_by_fips[fips] = (
                        float(income_raw) if income_raw.lower() != "null" else 50_000.0
                    )
                except (TypeError, ValueError, IndexError):
                    continue

            for state_abbr, state_fips in states.items():
                smb_count = smb_by_fips.get(state_fips, 0)
                if smb_count <= 0:
                    logger.warning("Missing/invalid SMB count for %s; using default", state_abbr)
                    smb_count = 100_000

                median_income = income_by_fips.get(state_fips, 50_000.0)

                # Approximate state-level revenue proxy from household income + business counts.
                gdp_estimate = median_income * smb_count * 2.5

                normalized = _normalize_econ_indicator(state_abbr, smb_count, gdp_estimate)
                if normalized is None:
                    logger.debug("Skipped invalid economic indicator: %s", state_abbr)
                    continue

                state, smb_count, avg_revenue = normalized

                await _upsert_economic_indicator(
                    db,
                    state=state,
                    smb_count=smb_count,
                    avg_revenue=avg_revenue,
                )
                indicators_added += 1
                indicators_validated += 1

        await db.commit()
        print(
            f"✓ Ingested economic data for {indicators_added} states from Census API, validated {indicators_validated}"
        )

    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Census API error: %s. Falling back to CSV file.", e)
        await ingest_region_economics_from_csv(db)


async def ingest_region_economics_from_csv(
    db: AsyncSession,
    path: str = "data/region_econ.csv",
) -> None:
    """Ingest regional economic indicators from a CSV file (fallback/demo mode).

    Applies validation and normalization to all records.
    """
    indicators_added = 0
    indicators_validated = 0

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize and validate before storing
            normalized = _normalize_econ_indicator(
                state=row["Region"],
                smb_count=int(row["SMB_Count"]),
                avg_revenue=float(row["GDP"]),
            )
            if normalized is None:
                logger.debug("Skipped invalid economic indicator from CSV: %s", row.get("Region"))
                continue

            state, smb_count, avg_revenue = normalized

            await _upsert_economic_indicator(
                db,
                state=state,
                smb_count=smb_count,
                avg_revenue=avg_revenue,
            )
            indicators_added += 1
            indicators_validated += 1

    await db.commit()
    print(f"✓ Ingested economic data from {path}, validated {indicators_validated}")


async def ingest_region_economics(
    db: AsyncSession,
) -> None:
    """
    Main entry point: ingest from Census API if available, fall back to CSV.

    Args:
        db: Database session
    """
    await ingest_region_economics_from_census(db)
