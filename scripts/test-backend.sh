#!/bin/bash
# Cross-platform test script for backend

set -e

echo "Running backend tests..."
cd backend
pip install -r requirements.txt >/dev/null 2>&1 || true
pytest -v tests/
