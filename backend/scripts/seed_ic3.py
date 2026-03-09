#!/usr/bin/env python3
"""Seed ic3_incidents with published FBI IC3 annual report data.

Source: Official FBI IC3 Annual Reports
  - 2021: https://www.ic3.gov/Media/PDF/AnnualReport/2021_IC3Report.pdf
  - 2022: https://www.ic3.gov/Media/PDF/AnnualReport/2022_IC3Report.pdf
  - 2023: https://www.ic3.gov/Media/PDF/AnnualReport/2023_IC3Report.pdf

Run inside the Docker container:
    docker compose exec backend python -m scripts.seed_ic3
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, text

from app.db.engine import AsyncSessionLocal, close_db, init_db
from app.db.models import IC3Incident

# ---------------------------------------------------------------------------
# Published FBI IC3 data — national totals distributed across states/sectors.
# Complaint counts and losses are from the official IC3 annual reports.
# ---------------------------------------------------------------------------

# Top attack types with (complaint_count, total_loss_USD) per year — national
_NATIONAL = {
    2021: {
        "Business Email Compromise":       (19954,  2395953296),
        "Ransomware":                      (3729,    49207908),
        "Phishing/Vishing/Smishing/Pharming": (323972, 44213707),
        "Personal Data Breach":            (51829,  517021289),
        "Non-Payment/Non-Delivery":        (82478,  337493071),
        "Tech Support Fraud":              (23903,  347657432),
        "Investment Fraud":                (20561, 1455943193),
        "Identity Theft":                  (51629,  278267918),
        "Extortion":                       (39360,   60577410),
        "Romance or Confidence Fraud":     (24299,  956039739),
    },
    2022: {
        "Business Email Compromise":       (21832,  2742354049),
        "Ransomware":                      (2385,    34341835),
        "Phishing/Vishing/Smishing/Pharming": (300497, 52089159),
        "Personal Data Breach":            (58859,  742438136),
        "Non-Payment/Non-Delivery":        (51679,  281770073),
        "Tech Support Fraud":              (32538,  806551993),
        "Investment Fraud":                (30529, 3311742206),
        "Identity Theft":                  (27922,  189205367),
        "Extortion":                       (39416,   107926490),
        "Romance or Confidence Fraud":     (19021,  735882192),
    },
    2023: {
        "Business Email Compromise":       (21489,  2946830270),
        "Ransomware":                      (2825,    59641217),
        "Phishing/Vishing/Smishing/Pharming": (298878, 18728550),
        "Personal Data Breach":            (55851,  494071682),
        "Non-Payment/Non-Delivery":        (50523,  309648609),
        "Tech Support Fraud":              (37560,  924512049),
        "Investment Fraud":                (39570, 4570891723),
        "Identity Theft":                  (19778,  126203809),
        "Extortion":                       (48223,   133949880),
        "Romance or Confidence Fraud":     (17823,  652544805),
    },
}

# States and rough population-weight distribution (simplified)
_STATES = [
    ("CA", 0.117), ("TX", 0.088), ("FL", 0.065), ("NY", 0.059), ("PA", 0.038),
    ("IL", 0.038), ("OH", 0.035), ("GA", 0.032), ("NC", 0.031), ("MI", 0.030),
    ("NJ", 0.027), ("VA", 0.026), ("WA", 0.024), ("AZ", 0.022), ("MA", 0.021),
    ("TN", 0.020), ("IN", 0.020), ("MO", 0.018), ("MD", 0.018), ("WI", 0.018),
    ("CO", 0.017), ("MN", 0.017), ("SC", 0.015), ("AL", 0.015), ("LA", 0.014),
    ("KY", 0.013), ("OR", 0.013), ("OK", 0.012), ("CT", 0.011), ("UT", 0.010),
    ("IA", 0.009), ("NV", 0.009), ("AR", 0.009), ("MS", 0.009), ("KS", 0.009),
    ("NM", 0.006), ("NE", 0.006), ("ID", 0.005), ("WV", 0.005), ("HI", 0.004),
    ("NH", 0.004), ("ME", 0.004), ("MT", 0.003), ("RI", 0.003), ("DE", 0.003),
    ("SD", 0.003), ("ND", 0.002), ("AK", 0.002), ("VT", 0.002), ("WY", 0.002),
]

_SECTORS = [
    ("Finance",      0.25),
    ("Healthcare",   0.18),
    ("Technology",   0.15),
    ("Retail",       0.12),
    ("Government",   0.10),
    ("Education",    0.08),
    ("Manufacturing",0.07),
    ("Other",        0.05),
]


def _build_rows() -> list[dict]:
    rows = []
    for year, attacks in _NATIONAL.items():
        for attack_type, (nat_complaints, nat_loss) in attacks.items():
            for state, state_weight in _STATES:
                state_complaints = max(1, round(nat_complaints * state_weight))
                state_loss = nat_loss * state_weight
                for sector, sector_weight in _SECTORS:
                    count = max(1, round(state_complaints * sector_weight))
                    loss = state_loss * sector_weight
                    avg = loss / count if count else None
                    rows.append(
                        dict(
                            year=year,
                            attack_type=attack_type,
                            sector=sector,
                            state=state,
                            complaint_count=count,
                            loss_amount=round(loss, 2),
                            avg_loss_per_incident=round(avg, 2) if avg else None,
                        )
                    )
    return rows


async def main() -> None:
    await init_db()

    rows = _build_rows()
    print(f"Seeding {len(rows):,} IC3 incident rows ({len(_NATIONAL)} years × "
          f"{len(next(iter(_NATIONAL.values())))} attack types × "
          f"{len(_STATES)} states × {len(_SECTORS)} sectors)...")

    async with AsyncSessionLocal() as session:  # type: ignore[attr-defined]
        # Wipe existing rows so re-runs are idempotent
        await session.execute(delete(IC3Incident))
        await session.commit()

        objects = [IC3Incident(**r) for r in rows]
        session.add_all(objects)
        await session.commit()

    print(f"✓ Seeded {len(rows):,} IC3 incident rows successfully.")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
