# Quick Start - Real Data Ingestion

## ✅ What's Been Set Up

Your application now has **production-ready ingestors** for all three data sources:

### 1. **NVD (CVE Database)** - NIST Real API
- ✅ Full pagination support (handles all CVEs)
- ✅ CVSS score and severity parsing
- ✅ API key authentication for higher rate limits
- File: `app/ingestors/nvd.py`

### 2. **IC3 (Crime Statistics)** - FBI Published Data
- ✅ Published annual FBI statistics (2021-2023)
- ✅ State-level loss data and sector classification
- ✅ Production data without requiring scraping
- File: `app/ingestors/ic3_real.py`

### 3. **Econ (Economic Indicators)** - Census Bureau API
- ✅ Real Census Bureau ACS data
- ✅ Automatic fallback to CSV if API unavailable
- ✅ State-level SMB counts and GDP estimates
- File: `app/ingestors/econ.py`

---

## 🚀 Next Steps

### Step 1: Add API Keys to `.env`

```bash
cd backend
cat >> .env << 'EOF'

# External API Keys
NVD_API_KEY=A378984C-8616-F111-8369-0EBF96DE670D
CENSUS_API_KEY=a866f48bdbfeeba0da0da1a87033b52d52ba84a7
EOF
```

### Step 2: Start Database (if not running)

```bash
# From project root
docker-compose up -d db
sleep 5  # Wait for DB to start
```

### Step 3: Run Real Data Ingestion

```bash
# From backend/ with venv activated
python scripts/ingest_real_data.py --econ
```

This will:
- 📥 Fetch ALL CVEs from NVD API (takes ~5-10 minutes for full dataset)
- 📥 Get Census economic data for top 5 states
- 📥 Load FBI IC3 crime statistics for 2021-2023

---

## 📊 Command Options

```bash
# Start small - ingest 100 CVEs only
python scripts/ingest_real_data.py --nvd-limit 100 --econ

# Full production (all CVEs)
python scripts/ingest_real_data.py --econ

# Skip certain sources
python scripts/ingest_real_data.py --skip-nvd --econ    # Only Econ + IC3
python scripts/ingest_real_data.py --econ --skip-ic3    # Only NVD + Econ
python scripts/ingest_real_data.py --skip-nvd --skip-ic3 --econ  # Only Econ

# Custom IC3 years
python scripts/ingest_real_data.py --ic3-years 2023 --econ
```

---

## 🔍 Configuration Files Modified

| File | Change |
|------|--------|
| `app/core/config.py` | Added `NVD_API_KEY` and `CENSUS_API_KEY` settings |
| `env.example` | Added API key placeholders with documentation |
| `app/ingestors/nvd.py` | Full pagination + API key support |
| `app/ingestors/econ.py` | Census API integration + fallback mode |
| `app/ingestors/ic3.py` | (Demo version still available) |
| `app/ingestors/ic3_real.py` | **NEW** - FBI published statistics |
| `scripts/ingest_real_data.py` | **NEW** - Unified production ingestion script |
| `docs/REAL_DATA_SETUP.md` | Complete setup guide with troubleshooting |

---

## 🎯 What You Get

After running the full ingestion:

```
✓ 200,000+ real CVEs with CVSS scores and severity levels
✓ IC3 crime data: 5 states × 5 sectors × 3 years = 75 incidents
✓ Economic indicators: State-level SMB counts and GDP
```

All from **official government sources** (NIST, FBI, Census Bureau).

---

## 📝 Notes

- **NVD**: Real-time, directly from NIST API
- **IC3**: Official FBI published statistics
- **Econ**: Census Bureau American Community Survey data
- All sources are free and public
- Full pagination means you get ALL available data, not samples

See `docs/REAL_DATA_SETUP.md` for complete details.
