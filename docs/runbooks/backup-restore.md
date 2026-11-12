# Backup and restore runbook

## What Render provides

Production Postgres is on a paid plan ($6/month) in Oregon. The plan includes point-in-time recovery: the dashboard's **Recovery** page can restore the database to any timestamp in the past 3 days (a Pro workspace would extend this to 7 days). Read from the Render dashboard on 2026-11-11.

Point-in-time recovery covers only the last 3 days. It doesn't replace the drill below, which proves that a restore from a `pg_dump` taken outside Render works.

## Drill, quarterly

Both connection strings come only from environment variables set in the operator's shell for the session; neither value is ever written to a file. `HT_PROD_DATABASE_URL` is the external connection string from the Render dashboard. `HT_DRILL_PASSWORD` is any throwaway value. `HT_DRILL_DATABASE_URL` uses the `postgres` user and the `postgres` database on localhost, port 55432, with that throwaway password.

- Run `read -rsp "Paste prod URL: " HT_PROD_DATABASE_URL; echo` on its own line, wait for the prompt, then paste the URL; then `export HT_PROD_DATABASE_URL`. Don't paste several lines at once: `read` would take the next pasted line as the value.
- `umask 077`, so the dump is readable only by you.
- `pg_dump --format=custom --no-owner --no-acl --file "$HOME/ht-drill.dump" "$HT_PROD_DATABASE_URL"`
- `docker run --name ht-restore -e POSTGRES_PASSWORD="$HT_DRILL_PASSWORD" -p 127.0.0.1:55432:5432 -d postgres:15`
- `until docker exec ht-restore pg_isready -h 127.0.0.1 -U postgres; do sleep 1; done`
- `pg_restore --no-owner --dbname "$HT_DRILL_DATABASE_URL" "$HOME/ht-drill.dump"`
- Row counts on both sides for `organizations`, `users`, `memberships`, `assets`, `asset_software`, `asset_findings`, `scan_runs`, `agent_enrollments`, `audit_log`: `SELECT count(*) FROM <table>;`
  Count production in the same window as the dump. Tables still being written (for example `audit_log` and `scan_runs`) may differ only by rows created after the dump started; record that in Notes, not as a mismatch.
- From `backend/`, run `DATABASE_URL="$HT_DRILL_DATABASE_URL" alembic -c app/db/alembic.ini current`; it must print `053 (head)` or the then-current head. The inline `DATABASE_URL` is required because alembic otherwise reads the app settings (`backend/.env`), which point at a different database.
- Clean up: `docker rm -f ht-restore`, delete `"$HOME/ht-drill.dump"`.

## Rules

The dump contains personal data: keep it outside the repository, never upload it, delete it after the drill. `pg_dump` must be version 15 or newer. The dump and the restored database contain live invite tokens: treat both as credentials, and keep the restore container bound to loopback. Run the drill on a single-user machine: `pg_dump` receives the production connection string as an argument, which other local users can see in the process list.

## Rotating the database credential

Creating a new default credential on the database does not update the backend's `DATABASE_URL`, even though `render.yaml` links it with `fromDatabase`. If the old credential is revoked first, the next deploy's pre-deploy migration fails with `role "…" is not permitted to log in`, and the running instance can't open new connections. In order:

1. Create the new credential and make it the default.
2. Set the backend's `DATABASE_URL` to the new credential's **Internal** Database URL, then save and deploy.
3. Once the deploy is green and `/health` is OK, revoke the old credential.
4. After any later blueprint sync, check which credential `DATABASE_URL` resolves to.

Never type the connection string into a command line. Paste it only at the `read -rs` prompt, so it stays out of shell history.

## Drill log

| Date | pg_dump version | Tables compared | Counts match | Restore time | Notes |
|---|---|---|---|---|---|
