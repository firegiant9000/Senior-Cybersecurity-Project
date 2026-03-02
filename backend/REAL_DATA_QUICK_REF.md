# Real Data Ingestion - Quick Reference

## Your Situation Right Now ✅

You have **real production data** from three official government sources:

```
✅ 500 CVEs           (NIST NVD API)
✅ 30 IC3 incidents   (FBI published data)  
✅ 14 economic stats  (US Census Bureau API)
────────────────────
   544 real records   IN YOUR DATABASE NOW
```

---

## Ingest More Data (One Command)

### Add More CVEs (recommended for testing)
```bash
cd backend
source .venv/bin/activate
python scripts/ingest_nvd_no_key.py --limit 1000
```

**Time**: ~1 minute | **Result**: 1000 total CVEs in database

### Get Full CVE Database (once NVD key activates)
```bash
# After activating key at the email link:
python scripts/ingest_real_data.py --econ
```

**Time**: ~30 hours | **Result**: 335k+ CVEs

---

## What Each Script Does

| Script | Purpose | Time | Requires |
|--------|---------|------|----------|
| `ingest_nvd_no_key.py` | CVEs without API key | 30sec per 500 | None |
| `ingest_real_data.py` | All 3 sources (NVD + Econ + IC3) | Varies | NVD key activated |
| `ingest_real_data.py --skip-nvd --econ` | Just Econ + IC3 | ~1 sec | None |

---

## Verify Data in Database

```bash
# From any terminal:
cd backend
psql postgresql://postgres:postgres@localhost:5432/cyber_threat_db

# Inside psql:
SELECT COUNT(*) as cve_count FROM cves;
SELECT COUNT(*) as ic3_count FROM ic3_incidents;
SELECT COUNT(*) as econ_count FROM economic_indicators;

# Sample a CVE:
SELECT cve_id, severity, cvss_score FROM cves LIMIT 3;

\q  # Exit psql
```

---

## When NVD Key Activates

**1. You'll get an email** from nvd@nist.gov saying "API key activated"

**2. Re-run full ingestion**:
```bash
cd backend && source .venv/bin/activate
python scripts/ingest_real_data.py --econ
```

**3. Wait ~20-30 hours** for all 335k+ CVEs to download

**4. Your database will be** fully populated with real NIST data

---

## Files You Created

```
✅ app/ingestors/nvd.py              → NVD real API (enhanced)
✅ app/ingestors/econ.py             → Census API integration
✅ app/ingestors/ic3_real.py         → FBI published data
✅ scripts/ingest_real_data.py       → Master orchestrator
✅ scripts/ingest_nvd_no_key.py      → CVE-only (no API key)
✅ backend/NVD_API_ACTIVATION.md     → Activation guide
✅ REAL_DATA_STATUS.md               → Full status report
✅ REAL_DATA_QUICK_START.md          → Setup guide
```

---

## API Keys You Have

```
NVD:    A378984C-8616-F111-8369-0EBF96DE670D
Census: a866f48bdbfeeba0da0da1a87033b52d52ba84a7
```

Both in `.env`:
```bash
# View them:
cat backend/.env | grep -E "NVD|CENSUS"
```

---

## Next: Update Your API Routes

Your routes (`app/api/routes/`) should now query from the real database:

**Example**:
```python
# app/api/routes/v1/vulnerabilities.py

@router.get("/")
async def get_vulnerabilities(db: AsyncSession):
    result = await db.execute(select(CVE).limit(100))
    cves = result.scalars().all()
    return [
        {
            "id": cve.cve_id,
            "description": cve.description,
            "severity": cve.severity,
            "cvss_score": cve.cvss_score,
        }
        for cve in cves
    ]
```

---

## Production Data Status

| Source | Records | API Key | Status |
|--------|---------|---------|--------|
| NVD | 500 | Not needed | ✅ Working |
| NVD | 335k+ | Needed | ⏳ Awaiting activation |
| IC3 | 30 | None | ✅ Working |
| Econ | 14 | ✅ Active | ✅ Working |

---

## You're Ready to:

✅ Query real CVE data  
✅ Analyze real IC3 incidents  
✅ Show real economic indicators  
✅ Demo the full platform with **real** production data  
✅ Scale to 335k+ CVEs when NVD key activates  

**Everything is working.** Just keep adding data as needed!
