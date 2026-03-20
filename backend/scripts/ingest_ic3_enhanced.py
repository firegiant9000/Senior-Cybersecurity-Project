"""Real FBI IC3 data ingestion from official PDF reports.

This script scrapes actual IC3 annual reports from https://www.ic3.gov/
and extracts:
- Attack type distribution (BEC, Ransomware, Phishing, etc.)
- Financial impact by attack type
- Geographic data (state-level)
- Temporal trends across years

Data sources (official FBI IC3 annual reports):
- 2024: https://www.ic3.gov/Media/PDF/AnnualReport/2024_IC3Report.pdf
- 2023: https://www.ic3.gov/Media/PDF/AnnualReport/2023_IC3Report.pdf
- 2022: https://www.ic3.gov/Media/PDF/AnnualReport/2022_IC3Report.pdf

NOTE: This requires pdfplumber to parse PDF tables.
Install with: pip install pdfplumber
"""

import asyncio
import io
import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import from app when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("\u26a0\ufe0f  pdfplumber not installed. Install with: pip install pdfplumber")
    sys.exit(1)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import IC3Incident
from app.ingestors.ic3_real import get_sector_weights

logger = logging.getLogger(__name__)


# Official IC3 report URLs by year
IC3_REPORT_URLS = {
    2024: "https://www.ic3.gov/Media/PDF/AnnualReport/2024_IC3Report.pdf",
    2023: "https://www.ic3.gov/Media/PDF/AnnualReport/2023_IC3Report.pdf",
    2022: "https://www.ic3.gov/Media/PDF/AnnualReport/2022_IC3Report.pdf",
    2021: "https://www.ic3.gov/Media/PDF/AnnualReport/2021_IC3Report.pdf",
}

# Common attack types tracked by IC3 (based on official categories)
IC3_ATTACK_TYPES = [
    "Business Email Compromise",
    "Ransomware",
    "Phishing/Vishing/Smishing/Pharming",
    "Personal Data Breach",
    "Non-Payment/Non-Delivery",
    "Extortion",
    "Tech Support Fraud",
    "Investment Fraud",
    "Romance or Confidence Fraud",
    "Identity Theft",
]


async def fetch_ic3_pdf(year: int) -> bytes | None:
    """Download IC3 annual report PDF from FBI website.
    
    Args:
        year: Year to fetch (2022, 2023, or 2024)
        
    Returns:
        PDF bytes or None if fetch fails
    """
    if year not in IC3_REPORT_URLS:
        logger.error(f"No IC3 report URL configured for year {year}")
        return None
        
    url = IC3_REPORT_URLS[year]
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            print(f"📥 Downloading IC3 {year} report from FBI website...")
            print(f"   URL: {url}")
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            print(f"✓ Downloaded {len(response.content):,} bytes")
            return response.content
    except httpx.HTTPError as e:
        logger.error(f"Failed to download IC3 {year} report: {e}")
        print(f"❌ Failed to download IC3 {year} report: {e}")
        return None


def _is_skip_label(text: str) -> bool:
    """Return True if *text* is a header / footer label, not a crime type."""
    low = text.lower().strip()
    skip_phrases = [
        "crime type", "by complaint", "by loss", "total", "descriptors",
        "complaint count", "loss amount", "subject", "annual report",
        "table", "page", "continued", "internet crime", "ic3",
    ]
    return any(p in low for p in skip_phrases) or len(low) < 3


def parse_crime_type_table(pdf_pages) -> list[dict]:
    """Extract crime type statistics from IC3 PDF.

    Scans **all** pages for 2-column tables whose rows look like
    ``[crime_type_name, numeric_value]``.  This is resilient to year-
    over-year layout changes (different page numbers, merged tables, etc.).

    Returns:
        List of dicts with attack_type, complaint_count, total_loss
    """
    complaint_data: dict[str, int] = {}
    loss_data: dict[str, float] = {}

    for page in pdf_pages:
        tables = page.extract_tables()

        for table in tables:
            if not table:
                continue

            for row in table:
                if not row or len(row) < 2:
                    continue

                crime_type = str(row[0]).strip() if row[0] else ""
                value_str = str(row[1]).strip() if row[1] else ""

                if not crime_type or not value_str:
                    continue
                if _is_skip_label(crime_type):
                    continue

                value_clean = value_str.replace("$", "").replace(",", "").strip()

                try:
                    value = float(value_clean)
                except (ValueError, TypeError):
                    continue

                # Heuristic: values containing '$' or > 1 M are loss amounts
                if "$" in value_str or value > 1_000_000:
                    # Keep the larger value if we see duplicates
                    if crime_type not in loss_data or value > loss_data[crime_type]:
                        loss_data[crime_type] = value
                else:
                    if crime_type not in complaint_data or value > complaint_data[crime_type]:
                        complaint_data[crime_type] = int(value)

    # Merge complaint and loss data
    crime_stats: list[dict] = []
    all_crime_types = set(complaint_data.keys()) | set(loss_data.keys())

    for crime_type in all_crime_types:
        complaint_count = complaint_data.get(crime_type, 0)
        total_loss = loss_data.get(crime_type, 0.0)

        if complaint_count > 0 or total_loss > 0:
            crime_stats.append({
                "attack_type": crime_type,
                "complaint_count": complaint_count,
                "total_loss": total_loss,
                "avg_loss": total_loss / complaint_count if complaint_count > 0 else 0.0,
            })

    return crime_stats


_US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY",
}


def _looks_like_state_table(table: list[list]) -> bool:
    """Heuristic: does this table contain US state codes in the first column?"""
    state_hits = 0
    for row in table[1:6]:  # check first few data rows
        if row and row[0]:
            val = str(row[0]).strip().upper()
            if val in _US_STATE_CODES:
                state_hits += 1
    return state_hits >= 2


def parse_state_statistics(pdf_pages) -> list[dict]:
    """Extract state-level statistics from IC3 PDF.

    Uses two heuristics to find state tables:
    1. Header row contains 'state' + 'victim' or 'loss'
    2. First column contains recognisable 2-letter US state codes

    Returns:
        List of dicts with state, complaint_count, total_loss
    """
    state_stats: list[dict] = []
    seen_states: set[str] = set()

    for page in pdf_pages:
        tables = page.extract_tables()

        for table in tables:
            if not table or len(table) < 2:
                continue

            header = table[0] if table else []
            header_text = " ".join([str(cell).lower() for cell in header if cell])

            is_state_table = (
                ("state" in header_text and ("victim" in header_text or "loss" in header_text or "count" in header_text))
                or _looks_like_state_table(table)
            )
            if not is_state_table:
                continue

            for row in table[1:]:
                if not row or len(row) < 2:
                    continue

                state = str(row[0]).strip().upper() if row[0] else ""

                if state not in _US_STATE_CODES or state in seen_states:
                    continue

                # Try to extract victim count and loss from remaining columns
                nums: list[float] = []
                for cell in row[1:]:
                    if not cell:
                        continue
                    cleaned = str(cell).replace("$", "").replace(",", "").strip()
                    try:
                        nums.append(float(cleaned))
                    except (ValueError, TypeError):
                        continue

                if not nums:
                    continue

                # First number is usually victim/complaint count, second is loss
                victim_count = int(nums[0]) if nums else 0
                total_loss = nums[1] if len(nums) > 1 else 0.0

                if victim_count > 0:
                    state_stats.append({
                        "state": state,
                        "complaint_count": victim_count,
                        "total_loss": total_loss,
                    })
                    seen_states.add(state)

    return state_stats


async def parse_ic3_pdf(pdf_bytes: bytes, year: int) -> tuple[list[dict], list[dict]]:
    """Parse IC3 PDF to extract crime types and state statistics.

    Args:
        pdf_bytes: PDF file bytes
        year: Year of the report

    Returns:
        Tuple of (crime_stats, state_stats) lists
    """
    if not HAS_PDF:
        print("❌ pdfplumber not installed. Install with: pip install pdfplumber")
        return [], []
    
    crime_stats = []
    state_stats = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            print(f"📄 Parsing {len(pdf.pages)} pages from IC3 {year} report...")
            
            # Extract crime type statistics
            crime_stats = parse_crime_type_table(pdf.pages)
            print(f"✓ Extracted {len(crime_stats)} crime type statistics")
            
            # Extract state statistics
            state_stats = parse_state_statistics(pdf.pages)
            print(f"✓ Extracted {len(state_stats)} state statistics")
            
    except Exception as e:
        logger.error(f"Error parsing IC3 {year} PDF: {e}")
        print(f"❌ Error parsing PDF: {e}")
    
    return crime_stats, state_stats


async def ingest_ic3_real_data(db_url: str, years: list[int] | None = None) -> int:
    """Ingest real IC3 data from official FBI PDF reports.
    
    This function:
    1. Downloads IC3 annual reports from ic3.gov
    2. Parses PDF tables to extract attack types, losses, and state data
    3. Inserts real data into database
    
    Args:
        db_url: Database connection URL
        years: List of years to ingest (default: [2022, 2023, 2024])
        
    Returns:
        Number of incidents ingested
    """
    if years is None:
        years = [2024, 2023, 2022]  # Try in reverse order (newest first)

    if not HAS_PDF:
        print("❌ ERROR: pdfplumber not installed")
        print("   Install with: pip install pdfplumber")
        return 0

    # Create async engine and session
    engine = create_async_engine(db_url, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    incidents_added = 0

    async with async_session() as session:
        for year in years:
            print(f"\n{'='*60}")
            print(f"Processing IC3 data for {year}")
            print(f"{'='*60}")

            # Clear existing data for this year to avoid duplicates on re-run
            from sqlalchemy import delete as sa_delete
            await session.execute(
                sa_delete(IC3Incident).where(IC3Incident.year == year)
            )

            # Download PDF
            pdf_bytes = await fetch_ic3_pdf(year)
            if not pdf_bytes:
                print(f"⚠️  Skipping {year} - PDF download failed")
                continue

            # Parse PDF
            crime_stats, state_stats = await parse_ic3_pdf(pdf_bytes, year)
            
            if not crime_stats:
                print(f"⚠️  Skipping {year} - no crime data extracted from PDF")
                continue
            
            # Build state shares: either from parsed state data or population estimates
            from app.ingestors.ic3_real import STATE_POPULATION_SHARES

            if state_stats:
                total_state_loss = sum(s["total_loss"] for s in state_stats) or 1
                state_shares = [
                    (s["state"], s["total_loss"] / total_state_loss)
                    for s in state_stats
                ]
            else:
                print(f"ℹ️  No state breakdown found, distributing across US states by population")
                state_shares = STATE_POPULATION_SHARES

            year_added = 0
            for crime in crime_stats:
                sector_weights = get_sector_weights(crime["attack_type"])

                for sector, sector_weight in sector_weights:
                    sector_complaints = max(1, int(crime["complaint_count"] * sector_weight))
                    sector_loss = crime["total_loss"] * sector_weight

                    for state, state_share in state_shares:
                        state_complaints = max(1, int(sector_complaints * state_share))
                        state_loss = sector_loss * state_share

                        if state_loss < 100 and state_complaints <= 1:
                            continue

                        avg_loss = state_loss / state_complaints if state_complaints > 0 else 0.0

                        session.add(IC3Incident(
                            year=year,
                            attack_type=crime["attack_type"],
                            sector=sector,
                            state=state,
                            complaint_count=state_complaints,
                            loss_amount=float(state_loss),
                            avg_loss_per_incident=avg_loss,
                        ))
                        year_added += 1
                        incidents_added += 1

            print(f"✓ Added {year_added} incident records for {year} ({len(crime_stats)} crime types × {len(state_shares)} states × sectors)")
        
        await session.commit()
        print(f"\n{'='*60}")
        print(f"✓ TOTAL: Ingested {incidents_added} IC3 incidents from FBI PDF reports")
        print(f"{'='*60}\n")
    
    await engine.dispose()
    return incidents_added


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost/cybersecurity_db"
    )
    
    count = asyncio.run(ingest_ic3_real_data(db_url))
    print(f"✓ Ingested {count} IC3 incidents from official FBI IC3 real data")
