# BEA - Bureau of Economic Analysis

## What It Does

Fetches and ingests **state-level economic indicators** from the U.S. Bureau of Economic Analysis API to provide regional context for SMB cybersecurity risk assessment.

## How to Refresh Data

### Run the Ingestion Script

```bash
cd backend
source ./venv/bin/activate
python scripts/ingest_real_data.py --econ
```

This will:
1. Query BEA API for state GDP and economic data
2. Calculate SMB density per state
3. Estimate state-level business metrics
4. Store in PostgreSQL

### View Data on Dashboard

Open `http://localhost:5173` and click the **"Economics"** tab to see:
- State-level SMB counts
- Average revenue by state
- Economic indicators ranked by SMB concentration
- Risk context for cybercrime data

## API Endpoints

- `GET /api/v1/economics/indicators` - List all state indicators
- `GET /api/v1/economics/indicators?sort_by=smb_count&sort_order=desc` - Highest SMB density
- `GET /api/v1/economics/indicators?page=1&page_size=10` - Paginated results

## Data Source

- BEA Regional Data API: https://apps.bea.gov/api/data
- Uses real state GDP, employment, and business data
- Estimates SMB counts from census data

## How It Works

The system uses:
1. **State GDP** from BEA Regional Economic Accounts
2. **Business employment data** to estimate firm sizes
3. **Census data** for SMB population estimates
4. Correlates with cybercrime data to show economic impact

## Files

- `backend/app/ingestors/econ.py` - Ingestion logic
- `backend/app/repositories/economics.py` - Database queries
- `backend/app/schemas/economics.py` - Response schemas
- `backend/app/api/routes/v1/economics.py` - API endpoints

## Configuration

The BEA API uses a public User ID. No authentication required.
