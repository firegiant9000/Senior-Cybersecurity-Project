@echo off
REM Start services with docker compose (Windows)

docker compose up -d
echo Services started. Backend: http://localhost:8000, Frontend: http://localhost:5173
