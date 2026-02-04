# Cyber Threat Intelligence & Anomaly Detection Platform

Production-ready monorepo for aggregating, analyzing, and detecting cyber threats across multiple data sources. This repo is organized for easy extension of integrations (CISA KEV, NVD, Shodan, etc.) and background ingestion jobs.

## Who this is for

- **New to the project**: Start with the overview and quick start below.
- **Frontend developers**: See the Frontend Guide section for app structure, API access, and local dev setup.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL, SQLAlchemy 2.0 (async), Alembic
- **Frontend**: React + TypeScript (Vite)
- **Dev tooling**: Docker, Ruff, pytest

## Monorepo Layout

```
.
├── backend/        # FastAPI application
├── frontend/       # React + Vite app
├── docs/           # Project docs
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Quick Start (Docker)

```
cp .env.example .env
make up
make migrate
```

- Backend: http://localhost:8000/health
- Frontend: http://localhost:5173

Stop services:

```
make down
```

## Quick Start (Local, No Docker)

### Backend

```
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```
cd frontend
npm install
npm run dev
```

## Frontend Guide (For New Contributors)

### Purpose

The frontend provides a minimal UI scaffold for the platform. It includes routing and a placeholder home page that calls the backend health endpoint. The UI will evolve later; keep changes minimal and modular.

### Key Paths

- App entry: frontend/src/main.tsx
- Routing: frontend/src/App.tsx
- Page components: frontend/src/pages/
- API clients: frontend/src/api/

### Environment Configuration

The frontend expects a backend URL via:

```
VITE_API_BASE_URL=http://localhost:8000
```

If not set, it defaults to http://localhost:8000 in frontend/src/api/health.ts.

### Add a New Page

1) Create a new page component in frontend/src/pages/.
2) Add a route in frontend/src/App.tsx.

### Call the Backend API

Use the API client pattern in frontend/src/api/health.ts:

```
export async function checkHealth(): Promise<HealthResponse> {
	const response = await fetch(`${API_BASE_URL}/health`)
	if (!response.ok) throw new Error(...)
	return response.json()
}
```

Create new API client files under frontend/src/api/ to keep requests organized.

### Frontend Commands

```
cd frontend
npm install
npm run dev
npm run build
npm run lint
npm run format
```

## Backend API Basics

- GET /health
- GET /api/v1/health

## Useful Commands

See docs/COMMANDS.md for a complete command reference and onboarding steps.

## Integrations & Workers

- Integrations live under backend/app/integrations/
- Background ingestion jobs live under backend/app/workers/

Use these directories as the primary extension points for new data sources and scheduled ingestion jobs.