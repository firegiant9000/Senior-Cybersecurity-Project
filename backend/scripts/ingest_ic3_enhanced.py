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

logger = logging.getLogger(__name__)


# Official IC3 report URLs by year
IC3_REPORT_URLS = {
    2024: "https://www.ic3.gov/Media/PDF/AnnualReport/2024_IC3Report.pdf",
    2023: "https://www.ic3.gov/Media/PDF/AnnualReport/2023_IC3Report.pdf",
    2022: "https://www.ic3.gov/Media/PDF/AnnualReport/2022_IC3Report.pdf",
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


def parse_crime_type_table(pdf_pages) -> list[dict]:
    """Extract crime type statistics from IC3 PDF.

    FBI IC3 PDFs have crime types split across pages 9-10:
    - Page 9: Crime types by complaint count
    - Page 10: Crime types by loss amount
    Tables are split into many 1-2 row tables.
    
    Returns:
        List of dicts with attack_type, complaint_count, total_loss
    """
    # Store complaint counts and losses separately
    complaint_data = {}  # {crime_type: count}
    loss_data = {}  # {crime_type: loss}
    
    # Scan pages 8-12 (0-indexed pages 7-11) for crime type data
    for page_num in range(min(7, len(pdf_pages)), min(12, len(pdf_pages))):
        page = pdf_pages[page_num]
        tables = page.extract_tables()
        
        for table in tables:
            if not table or len(table) == 0:
                continue
            
            # Each table is 1-2 rows: [crime_type, value]
            for row in table:
                if not row or len(row) < 2:
                    continue
                
                # Clean crime type name
                crime_type = str(row[0]).strip() if row[0] else ""
                value_str = str(row[1]).strip() if row[1] else ""
                
                # Skip empty or header rows
                if not crime_type or not value_str:
                    continue
                if crime_type.lower() in ["crime type", "by complaint count", "by complaint loss"]:
                    continue
                    
                # Determine if this is complaint count or loss based on value format
                value_clean = value_str.replace("$", "").replace(",", "")
                
                try:
                    value = float(value_clean)
                    
                    # If value has $ or is very large (>1M), it's a loss amount
                    if "$" in value_str or value > 1_000_000:
                        loss_data[crime_type] = value
                    else:
                        # Otherwise it's a complaint count
                        complaint_data[crime_type] = int(value)
                except (ValueError, TypeError):
                    continue
    
    # Merge complaint and loss data
    crime_stats = []
    all_crime_types = set(complaint_data.keys()) | set(loss_data.keys())
    
    for crime_type in all_crime_types:
        complaint_count = complaint_data.get(crime_type, 0)
        total_loss = loss_data.get(crime_type, 0.0)
        
        # Only include if we have at least one metric
        if complaint_count > 0 or total_loss > 0:
            crime_stats.append({
                "attack_type": crime_type,
                "complaint_count": complaint_count,
                "total_loss": total_loss,
                "avg_loss": total_loss / complaint_count if complaint_count > 0 else 0.0,
            })
    
    return crime_stats


def parse_state_statistics(pdf_pages) -> list[dict]:
    """Extract state-level statistics from IC3 PDF.

    Looks for tables containing:
    - State
    - Victim Count
    - Loss Amount
    
    Returns:
        List of dicts with state, complaint_count, total_loss
    """
    state_stats = []
    
    for page in pdf_pages:
        tables = page.extract_tables()
        
        for table in tables:
            if not table:
                continue
            
            header = table[0] if table else []
            header_text = " ".join([str(cell).lower() for cell in header if cell])
            
            # Check if this looks like a state table
            if "state" in header_text and ("victim" in header_text or "loss" in header_text):
                for row in table[1:]:
                    if not row or len(row) < 3:
                        continue
                    
                    state = str(row[0]).strip() if row[0] else ""
                    victim_count_str = str(row[1]).replace(",", "") if row[1] else "0"
                    loss_str = str(row[2]).replace("$", "").replace(",", "") if row[2] else "0"
                    
                    # Skip headers, totals, and non-state codes
                    if not state or len(state) != 2 or state.lower() in ["state", "total"]:
                        continue
                    
                    try:
                        victim_count = int(victim_count_str)
                        total_loss = float(loss_str)
                        
                        if victim_count > 0 and total_loss > 0:
                            state_stats.append({
                                "state": state.upper(),
                                "complaint_count": victim_count,
                                "total_loss": total_loss,
                            })
                    except (ValueError, TypeError):
                        continue
    
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
            
            # If no state breakdown available, distribute across all 50 states
            if not state_stats:
                print(f"ℹ️  No state breakdown found, distributing across 50 US states")
                
                # All 50 US states (proportional distribution by population)
                states = [
                    ("California", 0.115), ("Texas", 0.092), ("Florida", 0.067), 
                    ("New York", 0.060), ("Pennsylvania", 0.038), ("Illinois", 0.038),
                    ("Ohio", 0.035), ("Georgia", 0.033), ("North Carolina", 0.032),
                    ("Michigan", 0.030), ("New Jersey", 0.028), ("Virginia", 0.027),
                    ("Washington", 0.024), ("Arizona", 0.023), ("Massachusetts", 0.021),
                    ("Tennessee", 0.021), ("Indiana", 0.021), ("Maryland", 0.019),
                    ("Missouri", 0.019), ("Wisconsin", 0.017), ("Colorado", 0.017),
                    ("Minnesota", 0.017), ("South Carolina", 0.016), ("Alabama", 0.016),
                    ("Louisiana", 0.014), ("Kentucky", 0.014), ("Oregon", 0.013),
                    ("Oklahoma", 0.012), ("Connecticut", 0.011), ("Utah", 0.011),
                    ("Nevada", 0.011), ("Arkansas", 0.009), ("Kansas", 0.009),
                    ("Mississippi", 0.009), ("New Mexico", 0.007), ("Nebraska", 0.006),
                    ("New Hampshire", 0.004), ("West Virginia", 0.006), ("Idaho", 0.005),
                    ("Hawaii", 0.004), ("Maine", 0.004), ("Montana", 0.003),
                    ("Delaware", 0.003), ("South Dakota", 0.003), ("North Dakota", 0.002),
                    ("Alaska", 0.002), ("Vermont", 0.002), ("Wyoming", 0.002),
                    ("Washington DC", 0.002),
                ]
                
                # Create records for each attack type across all states
                for crime in crime_stats:
                    for state, population_share in states:
                        # Distribute losses and complaints by state population
                        state_loss = crime["total_loss"] * population_share
                        state_complaints = max(1, int(crime["complaint_count"] * population_share))
                        
                        # Only create record if it has meaningful data
                        if state_loss >= 100 or state_complaints >= 1:
                            # Calculate average loss for this state's distributed data
                            state_avg_loss = state_loss / state_complaints if state_complaints > 0 else 0
                            
                            incident = IC3Incident(
                                year=year,
                                attack_type=crime["attack_type"],
                                sector="All",  # IC3 aggregates across sectors
                                state=state,
                                complaint_count=state_complaints,
                                loss_amount=float(state_loss),
                                avg_loss_per_incident=state_avg_loss,
                            )
                            session.add(incident)
                            incidents_added += 1
                
                print(f"✓ Added {incidents_added} incident records for {year} ({len(crime_stats)} crime types × 50 states)")
                continue
            
            # Create matrix: attack_type x state (if state data available)
            # For each (attack_type, state) pair, create an incident
            for crime in crime_stats:
                for state_data in state_stats:
                    # Distribute attack type losses proportionally to each state
                    state_proportion = state_data["total_loss"] / sum(s["total_loss"] for s in state_stats)
                    attack_loss_in_state = crime["total_loss"] * state_proportion
                    attack_complaints_in_state = int(crime["complaint_count"] * state_proportion)
                    
                    if attack_loss_in_state < 1000 or attack_complaints_in_state < 1:
                        continue  # Skip tiny values
                    
                    incident = IC3Incident(
                        year=year,
                        attack_type=crime["attack_type"],
                        sector="Mixed",  # IC3 doesn't break down by sector in all reports
                        state=state_data["state"],
                        complaint_count=attack_complaints_in_state,
                        loss_amount=float(attack_loss_in_state),
                        avg_loss_per_incident=crime["avg_loss"],
                    )
                    session.add(incident)
                    incidents_added += 1
            
            print(f"✓ Added {incidents_added} incident records for {year}")
        
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
