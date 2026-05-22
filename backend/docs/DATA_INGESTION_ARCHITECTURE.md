# Data Ingestion Architecture

## Production Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    UPSTREAM SOURCES                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. NIST NVD API              2. FBI IC3 Reports        3. Census Bureau API
│     (Realtime CVEs)              (Annual Stats)            (ACS Data)
│     │                             │                        │
│     └─────────────────────────────┼────────────────────────┘
│                                   │
│                    ┌──────────────┴──────────────┐
│                    │  INGEST SCRIPTS             │
│                    │  (Real Data Mode)           │
│                    │                             │
│                    ├─ ingest_nvd()              │
│                    ├─ ingest_ic3_real()         │
│                    └─ ingest_region_economics() │
│
│  🎯 Master Script: ingest_real_data.py
│
│                    │
│                    ▼
│        ┌───────────────────────┐
│        │  PostgreSQL Database  │
│        ├───────────────────────┤
│        │ cves (200k+ rows)     │
│        │ ic3_incidents (75)    │
│        │ economic_indicators   │
│        └───────────────────────┘
│                    │
│                    ▼
│        ┌───────────────────────┐
│        │  API Routes           │
│        ├───────────────────────┤
│        │ GET /api/v1/...       │
│        │ - /vulnerabilities    │
│        │ - /ic3                │
│        │ - /economics          │
│        └───────────────────────┘
│                    │
│                    ▼
│         Frontend Dashboard
│
└─────────────────────────────────────────────────────────────┘
```

## Ingestion Command Paths

### Full Production Ingestion
```bash
python scripts/ingest_real_data.py --econ
# Runs:
# - ingest_nvd(db, max_results=None)     # All CVEs
# - ingest_ic3_real(db, years=[2021,22,23])
# - ingest_region_economics(db)           # Census API
# Time: ~5-10 minutes (depending on network)
```

### Quick Test (100 CVEs)
```bash
python scripts/ingest_real_data.py --nvd-limit 100 --econ
# Time: ~30 seconds
```

### Econ Only
```bash
python scripts/ingest_real_data.py --skip-nvd --skip-ic3 --econ
# Time: ~5 seconds
```

## Data Source Details

### 1. NVD (National Vulnerability Database)

**Endpoint**: `https://services.nvd.nist.gov/rest/json/cves/2.0`

**Authentication**: API Key (provided in .env as NVD_API_KEY)

**Data Retrieved**:
```json
{
  "cve_id": "CVE-2023-12345",
  "description": "...",
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "published_date": "2023-01-15"
}
```

**Rate Limits**:
- With key: 50 requests per 30 seconds
- Without key: 1 request per 6 seconds

**Pagination**: Automatic, fetches 2000 CVEs per request

---

### 2. IC3 (Internet Crime Complaint Center)

**Source**: Published FBI Annual Reports from ic3.gov

**Data Retrieved** (pre-populated from official reports):
```json
{
  "year": 2023,
  "state": "CA",
  "sector": "Finance",
  "loss_amount": 170000000
}
```

**Coverage**:
- States: CA, TX, NY, WA, FL
- Years: 2021, 2022, 2023
- Sectors: Finance, Healthcare, Tech, Energy, Manufacturing, Retail, etc.

**Total Rows**: ~75 (5 states × 5 sectors × 3 years)

---

### 3. Census Bureau API (Economic Indicators)

**Endpoint**: `https://api.census.gov/data/2021/acs/acs5`

**Authentication**: API Key (provided in .env as CENSUS_API_KEY)

**Data Retrieved**:
```json
{
  "state": "CA",
  "smb_count": 500000,
  "avg_revenue": 3.5e12
}
```

**Source**: American Community Survey (ACS) 5-Year Estimates

**Fallback**: Uses `data/region_econ.csv` if API unavailable

---

## Configuration Requirements

### Environment Variables (.env)

```ini
# Required for full functionality
NVD_API_KEY=<your-nvd-api-key-uuid>
CENSUS_API_KEY=<your-census-api-key>

# Optional (already in .env)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cyber_threat_db
```

Demo data is no longer toggled by a global env var. Seed a demo
organisation with `python -m scripts.seed_demo_org` instead — repositories
serve curated fixtures when the caller's org has `is_demo=true`.

### Python Settings (app/core/config.py)

```python
class Settings:
    NVD_API_KEY: str = ""         # Read from .env
    CENSUS_API_KEY: str = ""      # Read from .env
    # ... other settings
```

---

## Error Handling & Fallbacks

```
NVD Ingestion:
  ├─ Success → Populate cves table
  └─ API Error → Raise ValueError (requires API key)

IC3 Ingestion:
  ├─ Success → Populate ic3_incidents table
  └─ Error → Log warning, continue

Econ Ingestion:
  ├─ Census API Available → Use real Census data
  ├─ Census API Fails → Fallback to data/region_econ.csv
  └─ CSV Also Missing → Raise FileNotFoundError
```

---

## Next: API Route Updates

After ingestion completes, update API routes to serve this data:

**Current Endpoint** → **Updated Endpoint**
- `GET /api/v1/vulnerabilities` → Return from real CVE data
- `GET /api/v1/ic3` → Return from real IC3 incidents
- `GET /api/v1/economics` → Return from real economic indicators

See route files in `app/api/routes/` for current implementation.
