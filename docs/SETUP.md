# Setup Guide for New Team Members

This guide helps new developers get the project running locally.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Project Setup](#project-setup)
- [Using Docker Compose](#using-docker-compose)
- [Troubleshooting](#troubleshooting)
- [Windows-Specific Issues](#windows-specific-issues)

## Prerequisites

### Python 3.11+

**IMPORTANT**: Python 3.11 or 3.12 (NOT 3.14+, which causes Rust compile errors with pydantic-core).

Check your version:
```bash
python --version
```

**Install Python 3.11:**
- **Windows**: Download from https://www.python.org/downloads/ or `winget install Python.Python.3.11`
- **macOS**: `brew install python@3.11`
- **Linux**: `apt-get install python3.11`

**Verify installation (Windows):**
```bash
py -0p  # Lists all installed Python versions
py -3.11 --version  # Should show Python 3.11.x
```

### Node.js 18+ LTS

Check your version:
```bash
node --version
npm --version
```

**Install Node.js:**
- Download LTS from https://nodejs.org/
- Or via package manager:
  - **Windows**: `winget install OpenJS.NodeJS.LTS`
  - **macOS**: `brew install node`
  - **Linux**: `apt-get install nodejs npm`

### PostgreSQL 14+ (Optional for Docker)

If running locally without Docker, install PostgreSQL:
- **Windows**: https://www.postgresql.org/download/windows/
- **macOS**: `brew install postgresql`
- **Linux**: `apt-get install postgresql`

### Git & Git Bash (Windows Only)

Download from https://git-scm.com/download/win

### Docker & Docker Compose (Optional)

If you want to use containerized services:
- **Windows**: Install Docker Desktop from https://www.docker.com/products/docker-desktop
- **macOS**: Install Docker Desktop from https://www.docker.com/products/docker-desktop
- **Linux**: Install via package manager

## Project Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Senior-Cybersecurity-Project
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` and update if needed:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cyber_threat_db
APP_ENV=development
LOG_LEVEL=DEBUG
```

### 3. Setup Backend

```bash
cd backend

# Create Python 3.11 venv (use correct command for your OS)
py -3.11 -m venv venv              # Windows
python3.11 -m venv venv            # macOS/Linux

# Activate venv
# Git Bash (Windows):
source venv/Scripts/activate       
# Windows CMD:
venv\Scripts\activate              
# macOS/Linux:
source venv/bin/activate           

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Test installation
pytest -v tests/
```

### 4. Setup Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Run Locally (without Docker)

**Terminal 1 - Backend:**
```bash
cd backend
# Activate venv (adjust for your OS/shell)
source venv/Scripts/activate  # Git Bash
venv\Scripts\activate         # Windows CMD
source venv/bin/activate      # macOS/Linux

uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Using Docker Compose

If you have Docker installed:

```bash
make up
make migrate
```

- Backend: http://localhost:8000/health
- Frontend: http://localhost:5173
- Database: localhost:5432

Stop services:
```bash
make down
```

## Troubleshooting

### "No module named app" or import errors
- Ensure you're using Python 3.11+, not 3.14+
- Make sure venv is activated
- Verify: `python --version` should show 3.11.x or 3.12.x

### Vite PostCSS error
- Delete `frontend/node_modules`
- Run `npm install` again

### Database connection refused
- Ensure PostgreSQL is running (or use Docker)
- Check DATABASE_URL in .env
- If using Docker: `docker compose up postgres` first

### Port already in use
- Change ports in `.env` or `docker-compose.yml`
- Common ports: 5173 (frontend), 8000 (backend), 5432 (postgres)

## Windows-Specific Issues

### "make: command not found" in Git Bash

- Install: `winget install GnuWin32.Make`
- Then verify: `make --version`
- Or use direct commands instead: `docker compose up -d`

### Cannot run Python 3.11 (py -3.11 fails)

Python 3.11 isn't installed. Install it:
```bash
winget install Python.Python.3.11
```

Then verify all installed versions:
```bash
py -0p
```

You should see Python 3.11 in the list.

### "pydantic-core requires Rust" error

**Cause**: You're using Python 3.14+. The project needs Python 3.11 or 3.12.

**Solution**: Create a venv with Python 3.11:
```bash
py -3.11 -m venv venv
source venv/Scripts/activate  # or venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Git Bash venv activation syntax

In **Git Bash**, use forward slashes and `source`:
```bash
source venv/Scripts/activate
```

NOT:
```bash
venv\Scripts\activate  # This is Windows CMD syntax
```

In **Windows CMD**, use backslashes:
```bash
venv\Scripts\activate
```

### "pip: command not found" or "site-packages is not writeable"

Use `python -m pip` instead:
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Port 5173 or 8000 already in use

On Windows, find what's using the port:
```bash
netstat -ano | findstr :5173
netstat -ano | findstr :8000
```

Then either:
- Kill the process: `taskkill /PID <PID> /F`
- Or change the port in `.env` / `docker-compose.yml`

### Docker Compose "docker-compose: command not found"

Modern Docker uses `docker compose` (no hyphen). If you see errors:

```bash
# Old syntax (doesn't work)
docker-compose up

# New syntax (correct)
docker compose up
```

The Makefile has been updated to use the new syntax. If using Makefile:
```bash
make up
```

### Node.js version issues

If frontend won't start, check Node version:
```bash
node --version  # Should be 18+ LTS
npm --version   # Should be 9+
```

If outdated, download LTS from https://nodejs.org/

## Common Commands

| Task | Command |
|------|---------|
| Run backend tests | `cd backend && pytest -v tests/` |
| Lint backend | `cd backend && ruff check app tests` |
| Format backend | `cd backend && ruff format app tests` |
| Run frontend tests | `cd frontend && npm run test` (TODO) |
| Lint frontend | `cd frontend && npm run lint` |
| Database migrations | `make migrate` (Docker) or `alembic upgrade head` (local) |
| Docker up | `make up` or `docker compose up -d` |
| Docker down | `make down` or `docker compose down` |
| View logs | `make logs` or `docker compose logs -f` |

## File Structure

See [README.md](./README.md) for full structure and feature descriptions.

## Next Steps

1. Read [docs/COMMANDS.md](./docs/COMMANDS.md) for all available commands
2. Familiarize yourself with the [backend/app/](./backend/app/) structure
3. Check [frontend/src/](./frontend/src/) for React component layout
4. See [backend/app/integrations/](./backend/app/integrations/README.md) for adding new data sources

## Questions?

Open an issue on GitHub or ask the team on Slack/Discord.
