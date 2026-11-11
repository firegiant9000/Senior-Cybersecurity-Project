# Backup and restore runbook

## What Render provides

Production Postgres is on a paid plan in Oregon; the plan includes `<record here: point-in-time recovery window, or daily snapshots>`, read from the Render dashboard.

## Drill, quarterly

Both connection strings come only from environment variables set in the operator's shell for the session; neither value is ever written to a file. `HT_PROD_DATABASE_URL` is the external connection string from the Render dashboard. `HT_DRILL_PASSWORD` is any throwaway value, and `HT_DRILL_DATABASE_URL` points at the local container on port 55432 using it.

- `pg_dump --format=custom --no-owner --no-acl --file ht-drill.dump "$HT_PROD_DATABASE_URL"`
- `docker run --name ht-restore -e POSTGRES_PASSWORD="$HT_DRILL_PASSWORD" -p 55432:5432 -d postgres:15`
- `pg_restore --no-owner --dbname "$HT_DRILL_DATABASE_URL" ht-drill.dump`
- Row counts on both sides for `organizations`, `users`, `memberships`, `assets`, `asset_software`, `asset_findings`, `scan_runs`, `agent_enrollments`, `audit_log`: `SELECT count(*) FROM <table>;`
- `alembic current` against the restored database must print `053 (head)` or the then-current head.
- Clean up: `docker rm -f ht-restore`, delete `ht-drill.dump`.

## Rules

The dump contains personal data: keep it outside the repository, never upload it, delete it after the drill. `pg_dump` must be version 15 or newer.

## Drill log

| Date | pg_dump version | Tables compared | Counts match | Restore time | Notes |
|---|---|---|---|---|---|
