# Real Data Ingestion Setup Guide

## Overview

You now have production-ready ingestors that pull data from real upstream feeds:

1. **NVD (National Vulnerability Database)** - Real CVE data via NIST API
2. **IC3 (Internet Crime Complaint Center)** - Published FBI crime statistics  
3. **Econ (Economic Indicators)** - US Census Bureau data

## Prerequisites

### 1. Set Your API Keys in `.env`

Create or update `backend/.env` with your activated API keys:

```bash
# Your NVD API Key UUID (from: https://nvd.nist.gov/developers/confirm-api-key)
NVD_API_KEY=A378984C-8616-F111-8369-0EBF96DE670D

# Your Census API Key (from: https://api.census.gov/data/key_signup.html)
CENSUS_API_KEY=a866f48bdbfeeba0da0da1a87033b52d52ba84a7
```

### 2. Ensure Database is Running

```bash
# From root of project
docker-compose up -d db
```

## Usage

### Run Full Production Ingestion

From `backend/` directory with venv activated:

```bash
# Ingest all sources (NVD with no limit, Census, IC3 for 2021-2023)
python scripts/ingest_real_data.py --econ

# Or with custom NVD limit (useful for testing)
python scripts/ingest_real_data.py --nvd-limit 100 --econ

# Ingest only specific sources
python scripts/ingest_real_data.py --skip-ic3           # Skip IC3, get NVD + Census
python scripts/ingest_real_data.py --skip-nvd --econ    # Skip NVD, get IC3 + Census only

# Customize IC3 years
python scripts/ingest_real_data.py --ic3-years 2022,2023 --econ
```

### Individual Ingestors

Each ingestor can also be imported and used separately in your code:

```python
from app.ingestors.nvd import ingest_nvd
from app.ingestors.econ import ingest_region_economics
from app.ingestors.ic3_real import ingest_ic3_real

async with AsyncSessionLocal() as session:
    # Get first 500 CVEs from NVD
    await ingest_nvd(session, max_results=500)
    
    # Get Census economic data (falls back to CSV if API key missing)
    await ingest_region_economics(session)
    
    # Get IC3 data for specific years
    await ingest_ic3_real(session, years=[2023, 2022])
```

## Data Sources Explained

### NVD (nvd.py)

- **Source**: NIST National Vulnerability Database API
- **URL**: https://services.nvd.nist.gov/rest/json/cves/2.0
- **Rate Limits**:
  - Without API key: 1 request per 6 seconds
  - With API key: 50 requests per 30 seconds
- **Data Fetched**:
  - CVE ID
  - Description
  - CVSS Score (v2/v3)
  - Severity (Critical/High/Medium/Low)
- **Note**: Fetches in batches of 2,000 CVEs per request with full pagination

### IC3 (ic3_real.py)

- **Source**: Published FBI Internet Crime Complaint Center statistics
- **URL**: https://www.ic3.gov/Media/PDF/Y{year}stats.pdf
- **Current Implementation**: Pre-populated published annual statistics (2021-2023)
- **Data Fetched**:
  - Year
  - State
  - Sector (Finance, Healthcare, Tech, Energy, Manufacturing, etc.)
  - Loss amount (distributed per sector per state)
- **Note**: IC3 doesn't offer a public API; data is from published annual reports

### Econ (econ.py)

- **Source**: US Census Bureau American Community Survey (ACS) API
- **URL**: https://api.census.gov/data/2021/acs/acs5
- **Data Fetched**:
  - State
  - SMB Count (estimated from Census business data)
  - Average Revenue/GDP (based on median household income + state economic factors)
- **Fallback**: Uses `data/region_econ.csv` if API key not set
- **Note**: Uses 2021 ACS 5-year estimates (most recent complete data from Census)

## Troubleshooting

### "NVD_API_KEY environment variable not set"

Make sure you've added the key to `backend/.env` and activated your key at:
https://nvd.nist.gov/developers/confirm-api-key

### "Census API error"

If Census API fails, check:
1. API key is correct in `.env`
2. You activated it at: https://api.census.gov/data/key_signup.html
3. Network connectivity to api.census.gov

The script will automatically fall back to CSV data if Census API is unavailable.

### Database Connection Errors

Ensure PostgreSQL is running:
```bash
docker-compose ps
```

If not running:
```bash
docker-compose up -d db
```

## Configuration Reference

See `backend/app/core/config.py` for available settings:
- `NVD_API_KEY` - Your NIST NVD API key UUID
- `CENSUS_API_KEY` - Your Census Bureau API key
- `ENABLE_DEMO_MODE` - Set to `False` to disable demo ingestors

## Next Steps

1. **Run the full ingestion**: `python scripts/ingest_real_data.py --econ`
2. **Monitor progress**: Check console output for ✓ indicators
3. **Verify in database**: Query tables to confirm data is populated
4. **Update API routes**: Ensure `/api/v1/vulnerabilities`, `/api/v1/ic3`, `/api/v1/economics` routes serve this data

## Notes on Data Accuracy

- **NVD**: Real-time, directly from NIST (most accurate)
- **IC3**: Published aggregates from FBI annual reports (accurate but annual)
- **Econ**: Census Bureau surveys (accurate but updated annually)

All three sources are official government data sources suitable for production use.
