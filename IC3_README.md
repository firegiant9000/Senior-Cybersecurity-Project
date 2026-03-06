# IC3 Data Ingestion

## What It Does

Fetches and parses **real FBI cybercrime data** from official IC3 (Internet Crime Complaint Center) annual reports and displays it on the dashboard.

## How to Refresh Data

### Run the Ingestion Script

```bash
cd backend
source ./venv/bin/activate
python scripts/ingest_ic3_enhanced.py
```

This will:
1. Download official FBI IC3 PDF reports (2022, 2023, 2024)
2. Parse crime type statistics from pages 9-10 of each report
3. Extract complaint counts and loss amounts
4. Store data in PostgreSQL database

### View Data on Dashboard

Open `http://localhost:5173` and click the **IC3** tab to see:
- Total complaints and losses
- Attack types (Business Email Compromise, Ransomware, Phishing, etc.)
- Loss amounts per attack type
- Complaint statistics

## Current Data

- **10 incident records** from 2024 FBI IC3 report
- **17 unique attack types** extracted
- **$5.8 billion** in total reported losses
- **45,222 total complaints**

## Technical Details

### Data Source
- Official FBI IC3 annual reports from https://www.ic3.gov/Media/PDF/AnnualReport/

### Parsing Logic
- Uses `pdfplumber` library to extract tables from PDFs
- Scans pages 7-11 for crime type statistics
- Distinguishes complaint counts vs. loss amounts by value format
- Creates national aggregate records (state="US")

### API Endpoints
- `GET /api/v1/ic3/incidents` - List all incidents
- `GET /api/v1/ic3/analytics/dashboard-summary` - Summary statistics
- `GET /api/v1/ic3/analytics/attack-types` - Top attack types by loss

## Files

- `backend/scripts/ingest_ic3_enhanced.py` - Main ingestion script
- `backend/app/api/routes/v1/ic3.py` - API endpoints
- `backend/app/services/ic3_analytics.py` - Analytics service
- `backend/app/repositories/ic3.py` - Database queries
- `frontend/src/Dashboard.tsx` - IC3 tab UI

## Troubleshooting

### No Data Extracted
If parsing returns 0 records, the FBI may have changed their PDF format. Use the debug script:

```bash
python scripts/debug_ic3_pdf.py
```

This shows the actual table structure in the PDF so you can update the parsing logic.

### Download Failed
Ensure you have network access to ic3.gov. The script includes a User-Agent header for compatibility.
