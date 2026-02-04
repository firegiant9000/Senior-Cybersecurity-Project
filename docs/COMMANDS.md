# Project Commands & Quick Start

This document lists useful commands and quick-start steps for onboarding.

## Quick Start (Docker Compose)

1) Copy env template (optional for local overrides):
```bash
cp .env.example .env
```

2) Start services:
```bash
make up
```

3) Run database migrations:
```bash
make migrate
```

4) Open apps:
- Backend: http://localhost:8000/health
- Frontend: http://localhost:5173

5) Stop services:
```bash
make down
```

## Quick Start (Local, No Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Makefile Commands

### Docker / Services
- `make up` — Start all services in Docker
- `make down` — Stop all services
- `make logs` — Follow logs for all services
- `make backend-logs` — Follow backend logs
- `make frontend-logs` — Follow frontend logs

### Database
- `make migrate` — Apply migrations
- `make makemigrations message="..."` — Create a new migration
- `make rollback` — Roll back the last migration
- `make seed` — Seed database (placeholder)

### Backend Quality
- `make backend-test` — Run backend tests
- `make backend-lint` — Lint with Ruff
- `make backend-format` — Format with Ruff

### Frontend Quality
- `make frontend-install` — Install dependencies
- `make frontend-lint` — Lint frontend
- `make frontend-format` — Format frontend

### Local Dev Helpers
- `make venv` — Create Python venv
- `make install-local` — Install backend + frontend deps locally
- `make migrate-local` — Run Alembic locally
- `make test-local` — Run tests locally
- `make lint-local` — Lint locally

### Cleanup
- `make clean` — Remove caches, node_modules, dist

## Common Endpoints
- `GET /health`
- `GET /api/v1/health`

## Troubleshooting

### Database not ready
```bash
docker-compose ps
docker-compose logs postgres
```

### Port conflicts
Update ports in `docker-compose.yml` or `.env`.
