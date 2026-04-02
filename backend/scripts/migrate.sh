#!/bin/sh
set -e
cd /app
alembic -c app/db/alembic.ini upgrade head
