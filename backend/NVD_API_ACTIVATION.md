# 🔑 NVD API Key Activation Required

## Current Status

✅ **Econ**: Working (14 states ingested)
✅ **IC3**: Working (30 incidents ingested)
❌ **NVD**: Waiting for key activation (404 error)

---

## What You Need To Do

The NVD API endpoint works (confirmed with curl test), but **your API key needs to be activated** before it can be used.

### Step 1: Check Your Email

Look for an email from **nvd@nist.gov** with subject "API Key Request" containing:
- A link like: `https://nvd.nist.gov/developers/confirm-api-key`
- Your UUID

### Step 2: Activate the Key

1. **Click the link** in that email
2. **Verify your email address** 
3. **Click "Activate"** or similar button
4. **Wait 1-2 minutes** for activation to propagate

You may also have received an email with instructions on the activation page.

### Step 3: Test the Key

Once activated, run:
```bash
cd backend
source .venv/bin/activate
python scripts/ingest_real_data.py --nvd-limit 50 --econ
```

---

## Why 404?

```
NVD API Status:
✓ Endpoint exists: https://services.nvd.nist.gov/rest/json/cves/2.0
✓ Works without API key (rate limited)
❌ Your key hasn't been activated in their system yet

Error: "Client error '404 Not Found'"
Reason: API key validation failed (key not yet active in NVD database)
```

---

## Troubleshooting

### "Still getting 404 after activation?"

1. **Wait a few more minutes** - NVD system needs time to sync
2. **Check email for confirmation** - Look for "activation complete" message
3. **Try without API key** - Edit `nvd.py` to comment out API key line temporarily:
   ```python
   # headers = {"apiKey": api_key}
   ```
   This will work but you'll hit rate limits after ~6 requests.

### "Can't find the activation email?"

1. **Check spam folder**
2. **Check email associated with your API key request** 
3. **Request a new key**: https://nvd.nist.gov/developers/request-an-api-key

---

## In the Meantime

NVD will work in demo mode without the API key, but with rate limits:
- **Rate Limit**: 1 request per 6 seconds (without API key)
- **Can ingest**: ~600 CVEs per hour
- **Full dataset**: 335,466 CVEs (would take ~20+ hours)

To ingest without API key limits, Census API + IC3 are fully functional!

---

## Current Working Data

```
✅ Economic Indicators: 14 states
✅ IC3 Incidents: 30 records (2021-2023)
⏳ NVD CVEs: Waiting for API key activation
```

**Next Steps**:
1. Activate NVD API key in email
2. Re-run: `python scripts/ingest_real_data.py --econ`
3. All three sources will then be operational
