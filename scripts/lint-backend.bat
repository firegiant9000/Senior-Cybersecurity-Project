@echo off
REM Cross-platform lint script for backend (Windows)

echo Linting backend code...
cd backend
ruff check app tests
ruff format app tests --check
