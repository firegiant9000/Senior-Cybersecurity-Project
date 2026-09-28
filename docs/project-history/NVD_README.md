# NVD - National Vulnerability Database

## What It Does

Fetches and ingests **CVE (Common Vulnerabilities and Exposures) data** from the National Vulnerability Database with CVSS scores and severity ratings.

## How to Refresh Data

### Run the Ingestion Script

```bash
cd backend
source ./venv/bin/activate
# Ingest with limit (faster, rate-limited free API)
python scripts/ingest_real_data.py --nvd-limit 1000

# Or with API key (higher limit, if you have one)
export NVD_API_KEY="your_key_here"
python scripts/ingest_real_data.py --nvd-limit 10000
```

This will:
1. Download CVE data from NVD API (NIST)
2. Parse CVSS scores and severity ratings
3. Extract vulnerability descriptions
4. Store in PostgreSQL with publication dates

### View Data on Dashboard

Open `http://localhost:5173` and click the **"NVD CVEs"** tab to see:
- Total CVEs in database
- Severity distribution
- Recent CVE publications
- Vulnerability descriptions

## API Endpoints

- `GET /api/v1/nvd/cves` - List all CVEs with pagination
- `GET /api/v1/nvd/cves?severity=critical` - Filter by severity
- `GET /api/v1/nvd/cves?page=1&page_size=50` - Custom pagination

## Data Source

- Official NVD API: https://services.nvd.nist.gov/rest/json/cves/2.0
- Free API (rate-limited): ~5 requests per 30 seconds
- With API Key: Higher rate limits

## Getting an API Key (Optional)

1. Visit: https://nvd.nist.gov/developers/request-an-api-key
2. Request your free API key
3. Set environment variable: `export NVD_API_KEY="your_key"`

## Files

- `backend/app/ingestors/nvd.py` - Ingestion logic
- `backend/app/repositories/nvd.py` - Database queries
- `backend/app/schemas/nvd.py` - Response schemas
- `backend/app/api/routes/v1/nvd.py` - API endpoints
