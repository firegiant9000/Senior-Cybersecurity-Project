#!/bin/bash
# Cross-platform test script for backend

set -e

echo "Running backend tests..."
cd backend
pip install -r requirements.txt -r requirements-dev.txtpytest -v tests/
