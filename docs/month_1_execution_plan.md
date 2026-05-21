# Month 1 Execution Plan — Stabilize + Foundations

Reference doc for Month 1 of [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md). Branch `feature/week0-month1-foundations` (off `main`). Issue numbers map to the GitHub milestone *Month 1 — Stabilize + Foundations*.

**Status: all five workstreams are implemented in this branch.** Remaining items are operational (deploy, branch protection, manual staging verification) and tracked at the bottom of this doc.

---

## Phase B — Foundational rails

- [x] **B1 / #106 — CI pipeline.** `pytest`, `ruff` (lint + format), frontend `eslint` + `tsc --noEmit`, `vitest`, single-Alembic-head check (Python-based, exact), `alembic check` drift detection. See [.github/workflows/ci.yml](../.github/workflows/ci.yml).
- [x] **B2 / #105 — Observability.** Sentry SDK on backend + frontend (no-op when DSN unset), PII scrubber for keys (`authorization`, `cookie`, `password`, `secret`, `token`, `api_key`, `email`, `hostname`) and inline email regex, `RequestContextMiddleware` binding `request_id` (UUID or honored `X-Request-ID`), JSON log formatter pulling `request_id`/`org_id`/`user_id` from `ContextVars`. PII inventory in [docs/pii_inventory.md](pii_inventory.md).

## Phase C — Demo segregation + data lifecycle

- [x] **C1 / #107 — Per-org demo mode.** `organizations.is_demo` (migration 031), `audit_log` table, `seed_demo_org.py` script (two seeded orgs, idempotent). Repository selector switches by org. `ENABLE_DEMO_MODE` removed from config and all backend docs/scripts. Frontend `DemoBanner` gated on `AuthContext.orgIsDemo` + `!loading` to avoid flash.
- [x] **C2 / #108 — Data lifecycle.** `DELETE /api/v1/organizations/{id}` iterates 12 tenant-scoped tables explicitly (no FK cascade reliance); detaches users via `org_id → NULL`. `GET /api/v1/organizations/{id}/export` streams JSON incrementally per-table. Both write `audit_log`. Retention policy stub at [backend/app/services/retention.py](../backend/app/services/retention.py) (12 scans/asset, 365-day audit-log window — cron lands Month 4). Integration tests in [backend/tests/test_data_lifecycle.py](../backend/tests/test_data_lifecycle.py).

## Phase D — Transparency + polish

- [x] **D1 / #102 — Source-status badges.** Backend registry at [backend/app/services/data_status.py](../backend/app/services/data_status.py) is the single source of truth; exposed at `GET /api/v1/data-status`. Frontend `SourceBadge` + `useDataStatus` hook (cached singleton) render on every overview widget via `WIDGET_DATASET_KEY`. Human mirror in [docs/DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md).
- [x] **D2 / #103 — IC3 static labels.** All 7 IC3 Pydantic schemas (`schemas/ic3.py`, `schemas/ic3_analytics.py`) carry `source: str = IC3_SOURCE_LABEL` so every response advertises "FBI IC3 2023 annual report (static summary)".
- [x] **D3 / #104 — Threat dashboard polish.** New `ThreatOverviewWidget` with CVEs ingested, KEV count, high-severity count, top exploited vendors, avg risk, last-ingest timestamp (from `/api/v1/ingest/freshness`), and a plain-English CVSS/KEV/EPSS glossary card.
- [x] **D4 / #109 — Trust pack.** New docs: [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md), [DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md), [pii_inventory.md](pii_inventory.md), [privacy.md](privacy.md). New routes `/privacy` and `/data-handling`, linked from the dashboard user dropdown.

## Phase E — Cleanup + optional wedge

- [x] **E1 / #161 — Drop `technology_vendors`.** Migration 030 drops the orphan table; model, repo, schema, and the CSV-upload + admin CRUD endpoints all removed. No lingering imports.
- [x] **E2 / #110 — Domain checks.** `GET /organizations/{org_id}/domains/{domain_id}/external-checks` runs HIBP + Shodan + OTX + crt.sh, caches the payload on `org_domains.external_checks_data` for 24h (migration 032), and returns `cached: true` on hits within the window. Each upstream returns `skipped: true` when its key is unset, so a partial config never fails the call.

---

## Open items before declaring Month 1 done

Operational tasks the code change can't complete. Track as follow-up issues if not done this branch:

- [ ] **Branch protection on `main`** — requires repo-admin in GitHub UI (CI required, no direct pushes).
- [ ] **Set `SENTRY_DSN` + `VITE_SENTRY_DSN` in staging/prod** — observability is a no-op without these.
- [ ] **Run [backend/tests/test_data_lifecycle.py](../backend/tests/test_data_lifecycle.py) against the staging DB** to confirm cascade behaviour against real data shapes (local CI Postgres covers schema correctness).
- [ ] **Manual staging walk-through** — log in, view labeled dashboard, mark an org `is_demo`, delete a throwaway org, export it, hit an intentional 500 and confirm Sentry event with `request_id` + scrubbed payload.
- [x] **Sentry source-map upload for the frontend build** — Vite emits `hidden` sourcemaps; `deploy-frontend` job uploads them via `getsentry/action-release@v1` when `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` secrets are set, then strips `*.map` files from `dist/` before Firebase deploy so they aren't served publicly. Requires setting the three GitHub Actions secrets to activate; otherwise the step warns and is skipped.

## Pre-existing finding (out of scope, flag separately)

Real NVD + Census API keys were checked into four docs on `main` (not introduced by this branch): [backend/docs/REAL_DATA_SETUP.md](../backend/docs/REAL_DATA_SETUP.md), [backend/docs/DATA_INGESTION_ARCHITECTURE.md](../backend/docs/DATA_INGESTION_ARCHITECTURE.md), [backend/INGESTION_COMPLETE.md](../backend/INGESTION_COMPLETE.md), [backend/REAL_DATA_QUICK_REF.md](../backend/REAL_DATA_QUICK_REF.md). Scrubbed to placeholders on this branch. **Keys must still be rotated at NIST NVD and Census** — they remain valid in git history until rotated.

---

## Definition of done (this branch)

- [x] All 10 Month 1 issues implemented in code.
- [x] CI workflow enforces single Alembic head + drift.
- [x] `git grep ENABLE_DEMO_MODE` returns only intentional historical refs (docs/plan).
- [x] `docs/DATA_SOURCE_STATUS.md` covers every dashboard widget.
- [ ] CI green on the PR (verify after push).
- [ ] Manual staging verification (see open items above).
