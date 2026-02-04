#!/bin/bash
# Run database migrations

docker compose exec backend alembic upgrade head
