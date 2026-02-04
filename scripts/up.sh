#!/bin/bash
# Start services with docker compose

docker compose up -d
echo "Services started. Backend: http://localhost:8000, Frontend: http://localhost:5173"
