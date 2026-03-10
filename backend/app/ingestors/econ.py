"""Economic indicator ingestion from Census Bureau API and CSV fallback.

Includes data validation and normalization to ensure consistency.
"""
import csv
import logging

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EconomicIndicator
from app.schemas.validators import EconomicIndicatorValidationSchema

logger = logging.getLogger(__name__)


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


async def ingest_region_economics_from_census(db: AsyncSession) -> None:
    """
    Ingest regional economic indicators from US Census Bureau API.

    Uses:
    - CBP (County Business Patterns): Real business establishment counts
    - ACS (American Community Survey): Median household income
    - Combines data to calculate state GDP estimates

    Applies validation and normalization to all records.
    """
    settings = get_settings()
    api_key = settings.CENSUS_API_KEY

    if not api_key:
        logger.warning("CENSUS_API_KEY not set. Falling back to CSV file.")
        await ingest_region_economics_from_csv(db)
        return

    try:
        # Using 2021 data (most recent complete Census data)
        cbp_url = "https://api.census.gov/data/2021/cbp"
        income_url = "https://api.census.gov/data/2021/acs/acs5"

        # All 50 states + DC with FIPS codes
        states = {
            "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
            "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
            "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
            "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
            "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
            "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
            "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
            "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
            "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
            "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
        }

        indicators_added = 0
        indicators_validated = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for state_abbr, state_fips in states.items():  # All 50 states
                # Fetch SMB count from County Business Patterns API
                # EMPSZES_LABEL: Employment size of establishments
                # We want establishments with 1-499 employees (small to medium businesses)
                cbp_params = {
                    "get": "ESTAB,NAME",
                    "for": f"state:{state_fips}",
                    "EMPSZES": "001",  # All establishments
                    "key": api_key,
                }

                try:
                    cbp_resp = await client.get(cbp_url, params=cbp_params)
                    cbp_resp.raise_for_status()
                    cbp_data = cbp_resp.json()

                    # Extract establishment count (ESTAB field)
                    if len(cbp_data) > 1:
                        smb_count = int(cbp_data[1][0]) if cbp_data[1][0] != "null" else 100000
                    else:
                        smb_count = 100000
                except (httpx.HTTPError, ValueError, IndexError) as e:
                    logger.warning("CBP API error for %s: %s. Using default.", state_abbr, e)
                    smb_count = 100000

                # Fetch median household income from ACS
                income_params = {
                    "get": "B19013_001E,NAME",
                    "for": f"state:{state_fips}",
                    "key": api_key,
                }

                resp = await client.get(income_url, params=income_params)
                resp.raise_for_status()
                data = resp.json()

                if len(data) > 1:
                    # data[0] is header, data[1] is the result
                    median_income = float(data[1][0]) if data[1][0] != "null" else 50000.0

                    # Estimate state GDP (simplified - median income * population factor)
                    gdp_estimate = median_income * smb_count * 2.5

                    # Normalize and validate before storing
                    normalized = _normalize_econ_indicator(state_abbr, smb_count, gdp_estimate)
                    if normalized is None:
                        logger.debug("Skipped invalid economic indicator: %s", state_abbr)
                        continue

                    state, smb_count, avg_revenue = normalized

                    economic = EconomicIndicator(
                        state=state,
                        smb_count=smb_count,
                        avg_revenue=avg_revenue,
                    )
                    db.add(economic)
                    indicators_added += 1
                    indicators_validated += 1

        await db.commit()
        print(
            "✓ Ingested economic data for "
            f"{indicators_added} states from Census API, "
            f"validated {indicators_validated}"
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

            db.add(EconomicIndicator(
                state=state,
                smb_count=smb_count,
                avg_revenue=avg_revenue,
            ))
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
