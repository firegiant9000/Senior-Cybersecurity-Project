@echo off
REM Run database migrations (Windows)

docker compose exec backend alembic upgrade head
