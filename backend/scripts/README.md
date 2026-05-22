# Backend scripts

## Init DB and ingest CISA KEV

Creates the database tables (`cves`, `kev_catalog`, etc.) and populates them from the CISA Known Exploited Vulnerabilities catalog.

**Prerequisites**

- PostgreSQL running and `DATABASE_URL` set (e.g. in `backend/.env`; see `env.example`).
- **Use Python 3.12** for this project. On macOS, if `python3` is 3.14, install 3.12: `brew install python@3.12`. Then use `python3.12` for the steps below.
  - If you see: `role "postgres" does not exist`, set `DATABASE_URL` to use your macOS username (Homebrew’s default).

**One-time setup: venv with Python 3.12**

From the repo root:

```bash
cd backend
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Run init + ingest (from backend, with venv activated)**

```bash
cd backend
source .venv/bin/activate
python scripts/init_and_ingest_kev.py
```

The API serves exploited vulnerabilities from the database by default. Demo-mode behaviour is now opt-in **per organisation** (see `organizations.is_demo` and `backend/scripts/seed_demo_org.py`); there is no global toggle.

**Start the API**

Run from the **backend** directory so the `app` package is on the path. Use the venv’s Python so the worker has greenlet and all deps:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload
```

**Verify**

- Open: `http://localhost:8000/api/v1/vulnerabilities/exploited?page=1&page_size=5`
