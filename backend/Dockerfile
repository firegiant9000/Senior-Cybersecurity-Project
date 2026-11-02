FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377 AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Production Python dependencies (hash-locked)
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && pip uninstall -y setuptools wheel
# setuptools and wheel come from the base image, not requirements.txt, and nothing
# at runtime uses them. setuptools vendors outdated copies of wheel and
# jaraco.context (CVE-2026-24049, CVE-2026-23949), so remove rather than patch.

# Dev stage: base plus test and lint tools (used by docker-compose, never deployed)
FROM base AS dev
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt
# Same app copy and non-root user as production, so compose behaves as before
COPY . .
RUN mkdir -p /app/uploads \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Production stage. Keep this LAST: Render builds the final stage by default.
FROM base

# Copy application
COPY . .

# Create uploads directory and non-root user
RUN mkdir -p /app/uploads \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
