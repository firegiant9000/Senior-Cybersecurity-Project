"""IC3 real-data ingestion adapter.

This module provides the ``ingest_ic3_real`` function used by
``scripts/ingest_real_data.py``.

When ``use_pdf=False``, falls back to hardcoded published IC3 summary
statistics so that the database can be seeded without internet access
or PDF parsing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import IC3Incident

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sector estimation weights per attack type.
#
# FBI IC3 reports do NOT break down by industry sector.  These weights are
# estimates based on publicly available research on which industries are
# most targeted by each attack type (Verizon DBIR, IBM X-Force, etc.).
# They are used to distribute aggregate IC3 numbers across sectors so the
# dashboard heatmap has meaningful content.
# ---------------------------------------------------------------------------
ATTACK_SECTOR_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "Business Email Compromise": [
        ("Finance", 0.30), ("Healthcare", 0.15), ("Technology", 0.12),
        ("Government", 0.10), ("Retail", 0.10), ("Education", 0.08),
        ("Manufacturing", 0.08), ("Real Estate", 0.07),
    ],
    "Ransomware": [
        ("Healthcare", 0.25), ("Education", 0.18), ("Government", 0.18),
        ("Finance", 0.12), ("Manufacturing", 0.10), ("Technology", 0.09),
        ("Retail", 0.08),
    ],
    "Phishing/Vishing/Smishing/Pharming": [
        ("Finance", 0.22), ("Technology", 0.16), ("Healthcare", 0.14),
        ("Retail", 0.12), ("Education", 0.10), ("Government", 0.10),
        ("Manufacturing", 0.08), ("Real Estate", 0.08),
    ],
    "Personal Data Breach": [
        ("Healthcare", 0.24), ("Finance", 0.20), ("Retail", 0.14),
        ("Technology", 0.12), ("Education", 0.10), ("Government", 0.10),
        ("Manufacturing", 0.10),
    ],
    "Non-Payment/Non-Delivery": [
        ("Retail", 0.30), ("Finance", 0.15), ("Technology", 0.12),
        ("Manufacturing", 0.12), ("Real Estate", 0.10),
        ("Healthcare", 0.08), ("Education", 0.05), ("Government", 0.08),
    ],
    "Extortion": [
        ("Finance", 0.20), ("Healthcare", 0.18), ("Technology", 0.15),
        ("Retail", 0.12), ("Education", 0.10), ("Government", 0.10),
        ("Manufacturing", 0.08), ("Real Estate", 0.07),
    ],
    "Tech Support Fraud": [
        ("Retail", 0.20), ("Finance", 0.18), ("Healthcare", 0.14),
        ("Technology", 0.14), ("Education", 0.10), ("Government", 0.10),
        ("Manufacturing", 0.07), ("Real Estate", 0.07),
    ],
    "Investment Fraud": [
        ("Finance", 0.35), ("Technology", 0.15), ("Real Estate", 0.12),
        ("Retail", 0.10), ("Healthcare", 0.08), ("Education", 0.07),
        ("Government", 0.06), ("Manufacturing", 0.07),
    ],
    "Romance or Confidence Fraud": [
        ("Finance", 0.20), ("Retail", 0.15), ("Healthcare", 0.15),
        ("Technology", 0.12), ("Education", 0.10), ("Government", 0.08),
        ("Real Estate", 0.10), ("Manufacturing", 0.10),
    ],
    "Identity Theft": [
        ("Finance", 0.25), ("Healthcare", 0.20), ("Retail", 0.15),
        ("Technology", 0.10), ("Government", 0.10), ("Education", 0.08),
        ("Manufacturing", 0.07), ("Real Estate", 0.05),
    ],
    "Credit Card/Check Fraud": [
        ("Finance", 0.30), ("Retail", 0.25), ("Technology", 0.10),
        ("Healthcare", 0.08), ("Manufacturing", 0.07), ("Education", 0.06),
        ("Government", 0.07), ("Real Estate", 0.07),
    ],
    "Crimes Against Children": [
        ("Education", 0.30), ("Government", 0.20), ("Technology", 0.15),
        ("Healthcare", 0.12), ("Retail", 0.08), ("Finance", 0.08),
        ("Manufacturing", 0.04), ("Real Estate", 0.03),
    ],
}

# Default weights when an attack type is not in the mapping above.
_DEFAULT_SECTOR_WEIGHTS: list[tuple[str, float]] = [
    ("Finance", 0.20), ("Healthcare", 0.15), ("Technology", 0.13),
    ("Retail", 0.12), ("Education", 0.10), ("Government", 0.10),
    ("Manufacturing", 0.10), ("Real Estate", 0.10),
]


def get_sector_weights(attack_type: str) -> list[tuple[str, float]]:
    """Return sector weights for an attack type, with fuzzy fallback."""
    if attack_type in ATTACK_SECTOR_WEIGHTS:
        return ATTACK_SECTOR_WEIGHTS[attack_type]
    # Try partial match
    lower = attack_type.lower()
    for key, weights in ATTACK_SECTOR_WEIGHTS.items():
        if key.lower() in lower or lower in key.lower():
            return weights
    return _DEFAULT_SECTOR_WEIGHTS


# ---------------------------------------------------------------------------
# Hardcoded IC3 fallback data
#
# Sourced from published FBI IC3 annual report summaries.  These are real
# aggregate numbers for complaint counts and losses by crime type.
# Sector and state breakdowns are estimated (see ATTACK_SECTOR_WEIGHTS and
# STATE_POPULATION_SHARES above).
# ---------------------------------------------------------------------------
IC3_FALLBACK_DATA: dict[int, list[dict]] = {
    2021: [
        {"attack_type": "Phishing/Vishing/Smishing/Pharming", "complaint_count": 323972, "total_loss": 44_213_707.0},
        {"attack_type": "Non-Payment/Non-Delivery", "complaint_count": 82478, "total_loss": 337_493_071.0},
        {"attack_type": "Personal Data Breach", "complaint_count": 51829, "total_loss": 517_021_289.0},
        {"attack_type": "Identity Theft", "complaint_count": 51629, "total_loss": 278_267_918.0},
        {"attack_type": "Extortion", "complaint_count": 39360, "total_loss": 60_577_741.0},
        {"attack_type": "Tech Support Fraud", "complaint_count": 23903, "total_loss": 347_657_432.0},
        {"attack_type": "Investment Fraud", "complaint_count": 20561, "total_loss": 1_455_943_193.0},
        {"attack_type": "Romance or Confidence Fraud", "complaint_count": 24299, "total_loss": 956_039_739.0},
        {"attack_type": "Business Email Compromise", "complaint_count": 19954, "total_loss": 2_395_953_296.0},
        {"attack_type": "Credit Card/Check Fraud", "complaint_count": 16750, "total_loss": 172_998_385.0},
        {"attack_type": "Ransomware", "complaint_count": 3729, "total_loss": 49_207_908.0},
        {"attack_type": "Crimes Against Children", "complaint_count": 2167, "total_loss": 0.0},
    ],
    2022: [
        {"attack_type": "Phishing/Vishing/Smishing/Pharming", "complaint_count": 300497, "total_loss": 52_089_159.0},
        {"attack_type": "Personal Data Breach", "complaint_count": 58859, "total_loss": 742_438_136.0},
        {"attack_type": "Non-Payment/Non-Delivery", "complaint_count": 51679, "total_loss": 281_767_015.0},
        {"attack_type": "Extortion", "complaint_count": 39416, "total_loss": 54_335_128.0},
        {"attack_type": "Identity Theft", "complaint_count": 27922, "total_loss": 189_206_269.0},
        {"attack_type": "Tech Support Fraud", "complaint_count": 32538, "total_loss": 806_551_993.0},
        {"attack_type": "Investment Fraud", "complaint_count": 30529, "total_loss": 3_311_742_206.0},
        {"attack_type": "Romance or Confidence Fraud", "complaint_count": 19021, "total_loss": 735_882_714.0},
        {"attack_type": "Business Email Compromise", "complaint_count": 21832, "total_loss": 2_742_354_049.0},
        {"attack_type": "Credit Card/Check Fraud", "complaint_count": 22985, "total_loss": 264_968_992.0},
        {"attack_type": "Ransomware", "complaint_count": 2385, "total_loss": 34_316_778.0},
        {"attack_type": "Crimes Against Children", "complaint_count": 2587, "total_loss": 0.0},
    ],
    2023: [
        {"attack_type": "Phishing/Vishing/Smishing/Pharming", "complaint_count": 298878, "total_loss": 18_728_550.0},
        {"attack_type": "Personal Data Breach", "complaint_count": 55851, "total_loss": 1_462_830_306.0},
        {"attack_type": "Non-Payment/Non-Delivery", "complaint_count": 50523, "total_loss": 309_648_702.0},
        {"attack_type": "Extortion", "complaint_count": 48223, "total_loss": 74_820_699.0},
        {"attack_type": "Identity Theft", "complaint_count": 19778, "total_loss": 126_203_858.0},
        {"attack_type": "Tech Support Fraud", "complaint_count": 37560, "total_loss": 924_512_658.0},
        {"attack_type": "Investment Fraud", "complaint_count": 39570, "total_loss": 4_568_129_068.0},
        {"attack_type": "Romance or Confidence Fraud", "complaint_count": 17823, "total_loss": 652_544_805.0},
        {"attack_type": "Business Email Compromise", "complaint_count": 21489, "total_loss": 2_946_681_604.0},
        {"attack_type": "Credit Card/Check Fraud", "complaint_count": 17000, "total_loss": 173_625_104.0},
        {"attack_type": "Ransomware", "complaint_count": 2825, "total_loss": 59_641_545.0},
        {"attack_type": "Crimes Against Children", "complaint_count": 2361, "total_loss": 0.0},
    ],
}

# Approximate US state population shares for distributing national totals.
STATE_POPULATION_SHARES: list[tuple[str, float]] = [
    ("CA", 0.115), ("TX", 0.092), ("FL", 0.067), ("NY", 0.060),
    ("PA", 0.038), ("IL", 0.038), ("OH", 0.035), ("GA", 0.033),
    ("NC", 0.032), ("MI", 0.030), ("NJ", 0.028), ("VA", 0.027),
    ("WA", 0.024), ("AZ", 0.023), ("MA", 0.021), ("TN", 0.021),
    ("IN", 0.021), ("MD", 0.019), ("MO", 0.019), ("WI", 0.017),
    ("CO", 0.017), ("MN", 0.017), ("SC", 0.016), ("AL", 0.016),
    ("LA", 0.014), ("KY", 0.014), ("OR", 0.013), ("OK", 0.012),
    ("CT", 0.011), ("UT", 0.011), ("NV", 0.011), ("AR", 0.009),
    ("KS", 0.009), ("MS", 0.009), ("NM", 0.007), ("NE", 0.006),
    ("WV", 0.006), ("ID", 0.005), ("HI", 0.004), ("NH", 0.004),
    ("ME", 0.004), ("MT", 0.003), ("DE", 0.003), ("SD", 0.003),
    ("ND", 0.002), ("AK", 0.002), ("VT", 0.002), ("WY", 0.002),
    ("DC", 0.002),
]


async def _ingest_fallback(
    session: AsyncSession,
    years: Sequence[int],
) -> int:
    """Insert hardcoded IC3 data with sector estimation."""
    from sqlalchemy import delete as sa_delete

    incidents_added = 0

    for year in years:
        if year not in IC3_FALLBACK_DATA:
            print(f"  ⚠️  No fallback data for {year}, skipping")
            continue

        # Clear existing data for this year to avoid duplicates
        await session.execute(
            sa_delete(IC3Incident).where(IC3Incident.year == year)
        )

        crime_stats = IC3_FALLBACK_DATA[year]

        for crime in crime_stats:
            attack_type = crime["attack_type"]
            sector_weights = get_sector_weights(attack_type)

            for sector, weight in sector_weights:
                sector_complaints = max(1, int(crime["complaint_count"] * weight))
                sector_loss = crime["total_loss"] * weight

                # Distribute across states by population
                for state, pop_share in STATE_POPULATION_SHARES:
                    state_complaints = max(1, int(sector_complaints * pop_share))
                    state_loss = sector_loss * pop_share

                    if state_loss < 100 and state_complaints <= 1:
                        continue

                    avg_loss = state_loss / state_complaints if state_complaints > 0 else 0.0

                    session.add(IC3Incident(
                        year=year,
                        attack_type=attack_type,
                        sector=sector,
                        state=state,
                        complaint_count=state_complaints,
                        loss_amount=float(state_loss),
                        avg_loss_per_incident=avg_loss,
                    ))
                    incidents_added += 1

        print(f"  ✓ {year}: seeded {incidents_added} incident records")

    await session.commit()
    return incidents_added


async def ingest_ic3_real(
    session: AsyncSession,
    *,
    years: Sequence[int] | None = None,
    use_pdf: bool = True,
) -> int:
    """Ingest IC3 data using either PDF parsing or hardcoded fallback.

    Args:
        session: Active database session from the caller.
        years: Optional sequence of years to ingest.
        use_pdf: When False, use hardcoded published statistics.

    Returns:
        Number of records ingested.
    """
    resolved_years = list(years) if years is not None else [2021, 2022, 2023]

    if not use_pdf:
        return await _ingest_fallback(session, resolved_years)

    try:
        from scripts.ingest_ic3_enhanced import ingest_ic3_real_data
    except ImportError as exc:  # pragma: no cover
        logger.error("Unable to import IC3 enhanced ingestor: %s", exc)
        return 0

    return await ingest_ic3_real_data(
        db_url=settings.DATABASE_URL,
        years=resolved_years,
    )
