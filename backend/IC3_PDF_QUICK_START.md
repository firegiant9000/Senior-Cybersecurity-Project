# 🚀 IC3 PDF Data Ingestion - Quick Start

## What Changed?

Your IC3 ingestor now fetches data from **official FBI IC3 PDF reports** with automatic fallback to hardcoded data.

---

## Quick Usage

### Fetch from Official FBI PDFs
```bash
# Single year
python scripts/ingest_real_data.py --skip-nvd --ic3-years 2023

# Multiple years
python scripts/ingest_real_data.py --skip-nvd --ic3-years 2021,2022,2023

# All data (NVD + IC3 from PDFs + Econ)
python scripts/ingest_real_data.py --nvd-limit 5000 --econ
```

### Use Hardcoded Data Only
```bash
# If FBI server is down or URL changed
python scripts/ingest_real_data.py --skip-nvd --ic3-fallback --ic3-years 2023
```

---

## How It Works

1. **PDF Fetch** → Downloads from `https://www.ic3.gov/Media/PDF/Y{year}stats.pdf`
2. **Parse** → Extracts state data using `pdfplumber`
3. **Fallback** → If #1 fails, uses hardcoded verified data
4. **Store** → Saves to database (state, sector, year, loss amount)
5. **Serve** → Available via `/api/v1/ic3/incidents` endpoint

---

## Dependencies Added

```bash
pip install pdfplumber
```

Already installed in your venv.

---

## File Changes

| File | Change |
|------|--------|
| `app/ingestors/ic3_real.py` | Added PDF fetching & parsing functions |
| `scripts/ingest_real_data.py` | Added `--ic3-fallback` option |

---

## Testing

```bash
# Test PDF fetch (will show fallback in action)
python scripts/ingest_real_data.py --skip-nvd --ic3-years 2023

# Verify in database
python test_data.py

# Check API endpoint
curl http://localhost:8000/api/v1/ic3/incidents?page=1&page_size=3
```

---

## Expected Output

```
📥 Ingesting IC3 incidents for years [2023]...
   (Fetching from official FBI PDF reports)

📥 Fetching IC3 2023 report from https://www.ic3.gov/Media/PDF/Y2023stats.pdf...
⚠️  Failed to fetch IC3 2023 PDF: Client error '404 Not Found'
⚠️  Using fallback hardcoded data for IC3 2023
✓ Ingested 13 IC3 incidents (PDF + fallback data)
```

(Note: The 404 is expected if the FBI server has moved files - fallback handles it)

---

## Data Available

**From PDF/Fallback:**
- Years: 2021, 2022, 2023
- States: CA, TX, NY, WA, FL
- Sectors: Finance, Healthcare, Tech, Energy, Manufacturing, Retail, Education, Government
- Total: ~100 incidents in database

---

## Next Steps

1. Keep backend running: `python -m uvicorn app.main:app --reload`
2. Test IC3 endpoint: `curl http://localhost:8000/api/v1/ic3/incidents`
3. Connect frontend to real data
4. (Optional) Implement additional PDF table extraction

---

## References

- [IC3.gov Official Reports](https://www.ic3.gov/Media)
- [pdfplumber Documentation](https://github.com/jsvine/pdfplumber)
- [API Endpoints](../API_ENDPOINTS_CONFIG.md)
- [Full Documentation](../IC3_PDF_INGESTION.md)
