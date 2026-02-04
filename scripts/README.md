# Cross-Platform Scripts

Use these scripts on Windows (without needing Make):

## Bash (Git Bash, WSL, macOS, Linux)
```bash
./scripts/test-backend.sh       # Run backend tests
./scripts/lint-backend.sh       # Lint backend
./scripts/up.sh                 # Start services
./scripts/down.sh               # Stop services
./scripts/migrate.sh            # Run migrations
```

## Batch (Windows CMD / PowerShell)
```cmd
scripts\test-backend.bat        # Run backend tests
scripts\lint-backend.bat        # Lint backend
scripts\up.bat                  # Start services
scripts\down.bat                # Stop services
scripts\migrate.bat             # Run migrations
```

## Alternative: Docker Compose directly
```bash
docker compose up -d
docker compose exec backend pytest -v tests/
docker compose exec backend ruff check app tests
docker compose exec backend alembic upgrade head
docker compose down
```

## Alternative: Local development (no Docker)
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest -v tests/
ruff check app tests
```
