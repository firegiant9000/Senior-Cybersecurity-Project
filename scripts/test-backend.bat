@echo off
REM Cross-platform test script for backend (Windows)

echo Running backend tests...
cd backend
python -m pytest -v tests/
