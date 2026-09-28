# KEV - CISA Known Exploited Vulnerabilities

## What It Does

Fetches and ingests the **CISA Known Exploited Vulnerabilities catalog** - a curated list of vulnerabilities with confirmed active exploits.

## How to Refresh Data

### Run the Ingestion Script

```bash
cd backend
source ./venv/bin/activate
python scripts/ingest_real_data.py --cisa-kev
```

This will:
1. Download the latest KEV catalog from CISA
2. Parse and validate each vulnerability entry
3. Cross-reference with NVD CVE database
4. Store in PostgreSQL with due dates and exploitation status

### View Data on Dashboard

Open `http://localhost:5173` and click the **"CISA KEV"** tab to see:
- Exploited vulnerabilities with due dates
- Vendor and product information
- Severity scores
- Date added to KEV catalog

## API Endpoints

- `GET /api/v1/vulnerabilities/exploited` - List all KEV entries with pagination
- `GET /api/v1/vulnerabilities/exploited?sort_by=kev_date_added&sort_order=desc` - Sort by date

## Data Source

- Official CISA KEV JSON feed: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

## Files

- `backend/app/ingestors/cisa_kev.py` - Ingestion logic
- `backend/app/repositories/kev_catalog.py` - Database queries (if exists)
- `backend/app/api/routes/v1/vulnerabilities.py` - API endpoints
