#!/bin/bash
# Cross-platform lint script for backend

set -e

echo "Linting backend code..."
cd backend
ruff check app tests
ruff format app tests --check
