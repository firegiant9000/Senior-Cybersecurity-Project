# Month 2 Execution Plan — Onboarding Wedge + Inventory MVP

Reference doc for Month 2 of [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md). Builds on the foundation laid in [month_1_execution_plan.md](month_1_execution_plan.md) (CI, observability, demo segregation, data lifecycle, source-status badges, trust pack — all merged via PR #164 at commit `79f61ad`).

**Theme:** Make the platform *usable by a real SMB* without forcing them through the 5-step assessment intake. Users should be able to (a) sign up, (b) point us at *something* they own (domain, CSV inventory, or cloud tenant), and (c) get a meaningful dashboard inside their first session.

**Goal of the month:** A user who has only completed org name + primary domain can upload a CSV asset inventory (or connect M365), see their assets matched against KEV/NVD, and get a credible risk picture. Foundation laid here unblocks the Month 3 CPE-matcher go/no-go gate.

---

## Goal / Scope / Constraints

**Goal:** Collapse the onboarding wall and ship the inventory ingest path (CSV first, cloud auto-discovery as a parallel spike).

**Scope:**
- Onboarding refactor — make the assessment intake non-blocking, ship a "fast path" that gets users to a useful dashboard with org + domain only.
- New asset/inventory data model (`assets`, `asset_software`, `scan_runs`, `cpe_match_cache`) + migrations.
- CSV/SBOM upload endpoint + UI (drag-drop, preview/validate, commit, background match job).
- M365/Entra OAuth spike (behind feature flag) for cloud auto-discovery — does not block CSV path.
- EPSS ingestor wired into the scheduler (code already exists; not registered).
- Vendor alias table (multiple display names map to one canonical vendor; required for matcher quality in Month 3).

**Out of scope (deferred):**
- Full CPE matching service (Month 3 — but the data model has to be designed correctly *now*).
- Google Workspace OAuth (Month 3, follows M365 pattern).
- Agent/scanner enrollment + token auth (Month 4).
- Real (parsed) IC3 ingestion (Month 4+).
- Retention cron (designed Month 1, scheduled Month 4).

**Constraints:**
- No new third-party dependencies without explicit approval (per [CLAUDE.md](../CLAUDE.md)).
- Multi-tenant isolation: every new repo query MUST scope by `org_id` (lint check should be added in Phase B).
- New tables must land on `Alembic v034 → v037`; CI already enforces single-head + drift detection (Month 1, B1).
- All new sources must register in `services/data_status.py` so source badges keep working.
- Demo orgs (`is_demo=true`) must still work — fixtures for assets/inventory must be added alongside the model.

**Verification:**
- New user can sign up → create org with just name + domain → upload CSV → see assets table populated → see KEV/CVE matches against uploaded software within 2 min.
- M365 OAuth flow completes in staging (devices discovered, but not necessarily matched yet — spike).
- EPSS scores present in DB after first scheduled run.
- CI green: all existing tests + new test suites pass.

**Risks:** See [Risk Register](#risk-register) below.

---

## Phases (designed to run in parallel)

Phases A–D can be worked on concurrently by different teammates. Dependencies are called out at the top of each phase. Phase E (M365 spike) is fully independent. Phase F is integration-only and runs last.

| Phase | Owner-style | Depends on | Can start day 1? |
|-------|-------------|-----------|------------------|
| A — Data model | Backend lead | — | ✅ Yes |
| B — Onboarding collapse | Full-stack | — | ✅ Yes |
| C — CSV inventory upload | Backend + frontend | A (model) | After A1 lands |
| D — EPSS scheduling + vendor aliases | Backend | — | ✅ Yes |
| E — M365 OAuth spike | Full-stack | — | ✅ Yes |
| F — Integration + dashboards | Frontend | A, C, D | Last sprint |

Recommend two-week sprint cadence; A+B+D+E ship in Sprint 1, C+F ship in Sprint 2.

---

## Phase A — Asset/Inventory Data Model

**Purpose:** Land the schema *first* so every other phase can build against it. Get this in by end of Week 1 of Sprint 1 to unblock Phase C.

- [ ] **A1 — `assets` table.** Migration `v034_add_assets.py`. Columns: `id`, `org_id` (FK, indexed), `hostname`, `ip_address?`, `os_name?`, `os_version?`, `mac_address?`, `discovered_via` (enum: `csv_upload`, `m365`, `gws`, `agent`, `manual`), `first_seen`, `last_seen`, `is_active`, `metadata` (JSONB for source-specific fields), `created_at`, `updated_at`. Composite unique index on `(org_id, hostname, mac_address)` with NULL-safe matching (use COALESCE in unique constraint).
- [ ] **A2 — `asset_software` table.** Migration `v035_add_asset_software.py`. Columns: `id`, `asset_id` (FK), `org_id` (denormalized for query speed + RLS), `vendor`, `product`, `version?`, `cpe_uri?` (nullable; matcher fills this in Month 3), `source` (enum mirrors `discovered_via`), `first_seen`, `last_seen`, `created_at`. Index on `(org_id, vendor, product)` for matcher lookups.
- [ ] **A3 — `scan_runs` table.** Migration `v036_add_scan_runs.py`. Columns: `id`, `org_id`, `source` (enum: `csv_upload`, `m365`, `gws`, `agent`), `status` (`pending`/`running`/`succeeded`/`failed`/`partial`), `started_at`, `finished_at?`, `asset_count`, `software_count`, `error_message?`, `metadata` (JSONB), `triggered_by_user_id?`. Each upload = one scan_run. Lets users see "what I uploaded on what date" + supports rollback.
- [ ] **A4 — `cpe_match_cache` table.** Migration `v037_add_cpe_cache.py`. Pre-staged for Month 3 matcher: `id`, `vendor_normalized`, `product_normalized`, `version_normalized?`, `cpe_uri`, `confidence_score`, `last_verified_at`. Not populated in Month 2 but the table must exist so the matcher service can be developed against a real schema.
- [ ] **A5 — `vendor_aliases` table.** Migration also in `v037` (or split if cleaner). Columns: `id`, `canonical_vendor`, `alias`, `source` (enum: `manual`, `nvd`, `kev`, `community`). Seed file with ~50 common aliases (e.g., `Microsoft Corp` → `microsoft`, `Apache Software Foundation` → `apache`). Drives both KEV/NVD matching against uploaded inventory **and** the existing vendor watchlist deduplication.
- [ ] **A6 — Repositories.** Create `backend/app/repositories/assets.py`, `asset_software.py`, `scan_runs.py`, `vendor_aliases.py`. Follow patterns in `repositories/org_vendor.py`. All queries scoped by `org_id`.
- [ ] **A7 — Pydantic schemas.** `backend/app/schemas/asset.py`, `asset_software.py`, `scan_run.py`. Include `source: str` field on every response (Month 1 D2 convention).
- [ ] **A8 — Demo fixtures.** Extend `backend/scripts/seed_demo_org.py` to seed ~25 fake assets + ~80 software entries for the "Public Demo" org so the dashboard isn't empty for the no-login demo route.
- [ ] **A9 — Register sources** in `backend/app/services/data_status.py` so widgets that read from `assets` / `asset_software` get the right `SourceBadge` (real vs static-demo).
- [ ] **A10 — Tests.** Repository CRUD + uniqueness + org isolation. Add to `backend/tests/test_assets.py`, `test_scan_runs.py`.

**Deliverable:** Migrations applied locally + in CI, repositories return data, demo orgs seeded.

---

## Phase B — Onboarding Collapse

**Purpose:** Remove the 5-step wall in front of users. Today, `AssessmentIntakePage.tsx` forces a multi-stage form before the dashboard renders meaningful data. Per the validation interviews, this kills activation.

- [ ] **B1 — Audit current intake gating.** Spike (2 days max). Map every place where tier unlock / dashboard data depends on assessment fields. Output: a doc listing every coupling between intake completion and downstream features. Without this, the refactor is high-risk.
- [ ] **B2 — Decouple tier gating from intake completion.** Today `services/assessment_intake.py` computes tier from filled fields. Change: tier is computed from *any combination of* (a) org profile completeness, (b) inventory presence (assets > 0), (c) connected integrations (M365, etc.). Org name + verified domain alone should unlock Basic tier with a useful (if sparse) dashboard.
- [ ] **B3 — "Skip for now" on every intake step.** Each step in `AssessmentIntakePage.tsx` gets a clearly-styled skip button. Skipping records `intake_step_skipped` analytics event (see Phase F4) so we can see what users abandon.
- [ ] **B4 — Post-signup landing flow.** New user → org create (just name + primary domain) → "What's next?" card on the dashboard with three options: *Upload CSV inventory*, *Connect M365*, *Complete profile for richer insights*. Wire to `frontend/src/components/dashboard/NextStepsCard.tsx` (new).
- [ ] **B5 — Optional-field UI treatment.** Fields that are nice-to-have but not required get a "Optional — affects [feature]" inline hint (reuse existing `InfoTip` component). This signals value without blocking.
- [ ] **B6 — Tier preview refactor.** `useIntakePreview` already exists. Update it so it shows the *delta* — "Connect M365 to unlock vendor matching across 23 more devices" — rather than gating the whole UI.
- [ ] **B7 — Tests.** Frontend: skip-button flow, decoupled tier display. Backend: tier computed correctly with only org + domain present. Add to `backend/tests/test_assessment_intake.py`.

**Deliverable:** A new user can reach a populated dashboard with org name + domain in under 60 seconds.

---

## Phase C — CSV / SBOM Inventory Upload

**Purpose:** The primary Month 2 wedge. Depends on Phase A (model) but is otherwise independent of B, D, E.

- [ ] **C1 — Define canonical CSV format.** Headers: `hostname,ip_address,os_name,os_version,vendor,product,version,notes`. Document in [docs/inventory_csv_format.md](inventory_csv_format.md). Provide a sample CSV at `frontend/public/sample-inventory.csv` for users to download.
- [ ] **C2 — `POST /api/v1/inventory/uploads/csv/preview`.** Accepts multipart file upload. Returns `{ valid_rows, invalid_rows[{row_number, errors[]}], total_assets, total_software, would_create, would_update }`. No DB writes. Validation: required columns present, valid IPs (or empty), no duplicate hostnames within file, max 10k rows per upload. Returns request_id in audit log (Month 1 D-pattern).
- [ ] **C3 — `POST /api/v1/inventory/uploads/csv/import`.** Accepts the same payload + `confirm: true`. Creates a `scan_runs` row, parses + inserts/updates `assets` + `asset_software`. Idempotent by `(org_id, hostname)` — re-uploading the same CSV updates `last_seen` rather than duplicating. Writes audit log. Returns `scan_run_id` so the frontend can poll status.
- [ ] **C4 — `GET /api/v1/scan-runs/{id}` + `GET /api/v1/scan-runs?org_id=...`.** Status polling + list of past uploads. Required for the "review last upload" UX.
- [ ] **C5 — `GET /api/v1/assets`** (paginated, filterable by `is_active`, `vendor`, search by hostname) **+ `GET /api/v1/assets/{id}`** (returns asset + software list).
- [ ] **C6 — Background match job.** When an import finishes, enqueue a job that cross-references `asset_software` against `kev` + `exploited_vuln` tables. Even *without* the Month 3 CPE matcher, a simple vendor+product literal match gets us first-cut "your inventory has KEV-listed software" findings. Store matches in a new `asset_findings` view or a denormalized column on `asset_software`. Decision needed in C1 — flag for review.
- [ ] **C7 — `frontend/src/pages/UploadInventoryPage.tsx`** + `frontend/src/api/inventory.ts`, `frontend/src/api/assets.ts`. Drag-drop zone (no new lib — use native HTML5 file input + DataTransfer API), CSV preview table (first 20 rows + error list), confirm button, progress indicator polling `scan_runs/{id}`.
- [ ] **C8 — `frontend/src/pages/AssetsPage.tsx`** — paginated asset table, filter by vendor / KEV-match status, drill-down to per-asset software list. Reuse existing table patterns from `NvdTable.tsx`.
- [ ] **C9 — Source badges** on AssetsPage rows: `csv_upload` → real-from-user badge, `m365` → real-from-integration, etc.
- [ ] **C10 — Tests.**
  - Backend: malformed CSV rejected with clear errors; valid CSV idempotent; org isolation (org A's CSV doesn't appear in org B); race condition test (two simultaneous uploads).
  - Frontend: drag-drop UX, preview rendering, error display.
- [ ] **C11 — Sample SBOM (CycloneDX JSON) acceptance.** Stretch: same endpoint detects SBOM format by Content-Type + first byte, parses `components[]` into `asset_software`. Implement only if Phase A and C1–C10 land early.

**Deliverable:** End-to-end CSV upload, validation, import, asset list with KEV-matched findings.

---

## Phase D — EPSS + Vendor Aliases (Matcher Prep)

**Purpose:** Get the upstream data sources Month 3 will depend on flowing now. These are independent of A/B/C/E.

- [ ] **D1 — Schedule EPSS.** Code already exists in [backend/app/ingestors/epss.py](../backend/app/ingestors/epss.py) but is **not** registered in `_SOURCE_SCHEDULE_MAP` inside [backend/app/workers/scheduler.py](../backend/app/workers/scheduler.py). Add `INGEST_SCHEDULE_EPSS` env var (default daily at 02:00 UTC, post-NVD), register the job, ensure it uses the same advisory-lock + idempotency pattern as KEV/NVD.
- [ ] **D2 — EPSS storage.** Confirm the EPSS table exists (check `backend/app/db/`); if not, add `v038_add_epss_scores.py`. Columns: `cve_id` (FK), `epss_score`, `percentile`, `fetched_at`. PK on `cve_id`.
- [ ] **D3 — Expose EPSS via NVD API.** Update `GET /api/v1/nvd/{cve_id}` to include `epss_score` + `percentile` in response. Add to `schemas/nvd.py`.
- [ ] **D4 — Surface EPSS in UI.** Add an "Exploitability" column to `NvdTable.tsx` (with the existing `ConfidenceBadge` styling). Add a one-line glossary entry in `ThreatOverviewWidget.tsx` (Month 1 already has the CVSS/KEV explainer card — add EPSS).
- [ ] **D5 — Register EPSS in `data_status.py`** as a live source.
- [ ] **D6 — Seed vendor aliases.** With the table from A5 in place, seed ~50 hand-curated common aliases. Source: pull from existing `kev` + `nvd` tables' distinct `vendor` column, group by similarity (manual pass acceptable for v1).
- [ ] **D7 — Tests.** EPSS ingestor success path + idempotency + failure handling. Alias resolution unit tests.

**Deliverable:** EPSS scores in the DB, visible in the NVD table, vendor aliases ready for the Month 3 matcher.

---

## Phase E — M365 / Entra OAuth Spike (parallel, behind feature flag)

**Purpose:** Validate the cloud-auto-discovery path for the segment B users identified in the May 11 validation interview. Goal is a working spike, not a polished feature.

- [ ] **E1 — Register Azure AD app.** Document app ID, tenant config in `docs/m365_integration_notes.md`. Required scopes: `Device.Read.All`, `DeviceManagementManagedDevices.Read.All`, `User.Read`. Multi-tenant.
- [ ] **E2 — Feature flag.** Add `ENABLE_M365_INTEGRATION` to `backend/app/core/config.py`. Default off in prod, on in dev. Frontend reads via existing config endpoint.
- [ ] **E3 — `POST /api/v1/integrations/m365/consent`.** Returns Microsoft consent URL with state token (random, persisted to a short-lived table `oauth_states` — migration `v039`, TTL 10 min).
- [ ] **E4 — `GET /api/v1/integrations/m365/callback`.** Validates state, exchanges code for access + refresh token, encrypts and stores in new `integration_credentials` table (`v040`). Credentials are per-org. Use Fernet via `cryptography` lib (already in requirements per `requirements.txt`).
- [ ] **E5 — `integrations/m365.py` client.** Thin wrapper around Graph API. Method `list_managed_devices(org_id)` returns device list, mapped to `assets` rows via the `discovered_via='m365'` enum from A1.
- [ ] **E6 — "Sync now" button.** `POST /api/v1/integrations/m365/sync` → creates a `scan_runs` row + populates assets. Uses same code path as CSV import for asset creation (Phase C3's helper function).
- [ ] **E7 — Frontend.** `frontend/src/pages/IntegrationsPage.tsx` (new) with a single M365 card showing connect/disconnect/sync status. Behind `ENABLE_M365_INTEGRATION` flag.
- [ ] **E8 — Tests.** Mock Graph API; assert assets created on sync; assert state token validation rejects forged callbacks.
- [ ] **E9 — Document for Month 3.** Notes file capturing rate limits, refresh token expiry, edge cases (tenant doesn't have Intune, etc.) so Month 3 can productionize.

**Deliverable:** Internal team can connect a test M365 tenant in staging and see devices appear as assets.

---

## Phase F — Integration, Dashboards, Polish

**Purpose:** Tie everything together. Runs in Sprint 2 after A–E land.

- [ ] **F1 — Dashboard "Assets" tab.** Add to `TabBar.tsx`. Shows asset count, top vendors by asset count, KEV-matched assets count, last upload timestamp (from `scan_runs`).
- [ ] **F2 — Asset → CVE drill-down.** Click an asset → see its software → click a software entry → see matched CVEs (KEV first, then NVD). Wire to `GET /api/v1/assets/{id}/findings` (new endpoint).
- [ ] **F3 — Inventory health card.** New `frontend/src/components/dashboard/InventoryHealthCard.tsx` for the overview tab: `assets_total`, `assets_with_known_software`, `assets_with_kev_match`, `last_inventory_update` (with relative time + source badge).
- [ ] **F4 — Activation analytics.** Lightweight client-side event log to `POST /api/v1/analytics/events` with event types: `intake_step_skipped`, `csv_upload_started`, `csv_upload_completed`, `m365_connect_started`, `m365_connect_completed`, `dashboard_first_view`. Backend stores in new `activation_events` table (`v041`). Goal: prove that the onboarding collapse improves time-to-value. **Only collect non-PII metadata.**
- [ ] **F5 — Demo org assets.** Ensure the demo-org seeding from A8 surfaces in the new dashboard tab.
- [ ] **F6 — Refresh `DATA_SOURCE_STATUS.md`** to include EPSS, asset-inventory, M365.
- [ ] **F7 — End-to-end smoke test.** Playwright or manual: new user → sign up → create org → upload sample CSV → see KEV match → screenshot for the trust pack.
- [ ] **F8 — Update [docs/PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md)** with Month 2 results.

---

## Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|-----------|
| R1 | Intake refactor (B2) is deeper than estimated; tier gating logic is more coupled than it looks. | Medium | High | Phase B1 is a 2-day spike — if scope balloons, descope B2 and ship "skip for now" buttons only (B3). Tier decoupling can slip to Month 3. |
| R2 | CSV idempotency races (two uploads from same org concurrently). | Medium | Medium | Use `scan_runs.status` + an advisory lock keyed on `(org_id, 'csv_import')`. Same pattern as ingest locks today. |
| R3 | Vendor matching false positives without the Month 3 CPE matcher — users see noise. | High | Medium | Phase C6 — start with literal vendor+product match only; UI clearly labels as "preliminary match — Month 3 CPE matcher will refine." Use confidence badges. |
| R4 | M365 OAuth redirect URI mismatch between local/staging/prod. | Medium | Low | Document all three redirect URIs in E1; gate behind feature flag so prod isn't broken if config is wrong. |
| R5 | Large CSV uploads (>10k rows) time out the request. | Medium | Medium | C2 caps at 10k. For larger, accept async pattern: enqueue + return `scan_run_id` immediately. Show progress in UI. |
| R6 | EPSS endpoint changes / rate limits surprise us. | Low | Low | Existing ingestor already handles auth — just register the schedule. Monitor first run in staging. |
| R7 | New tables forget `org_id` index → slow queries at scale. | Medium | Medium | Add a backend CI check that greps for `Column("org_id"` without a matching `Index(`. Easy lint script. |
| R8 | Pre-existing NVD/Census key leak in git history (carried from Month 1) is still unrotated; pilots can't start until cleared. | High | Critical | **Block prod pilots** until keys are rotated. Track as ops-only item; don't gate Month 2 dev work on it but raise it in the next group standup. |
| R9 | Assessment intake's "skipped" state isn't preserved across logins, causing users to see the wall again. | Medium | High | Persist skip choices on `org_intake_state` table or on `User.preferences` JSONB. Decide in B3. |
| R10 | Activation analytics (F4) inadvertently logs PII (hostname, IP) from inventory uploads. | Medium | High | Reuse the Month 1 PII scrubber (`backend/app/core/observability.py`). All event payloads MUST pass through scrubber before being persisted. Add explicit test. |

---

## Issues that may come up given the current code

Concrete frictions discovered during code audit — call these out to the team early:

1. **`assessment_intake.py` is the linchpin of the user flow.** It currently computes tier from a closed set of required fields. The "make Basic useful without all fields" deliverable means rethinking this service. Recommend the B1 spike happen *before* anything else in Phase B is committed.
2. **`POST /api/v1/uploads` already exists for assessment payload files** — do **not** overload it with CSV inventory. Create a separate `inventory/uploads/csv/*` namespace to keep concerns separate (Phase C2/C3).
3. **`org_vendor` table is the existing watchlist** — we now have TWO ways for a vendor to appear in the system (manually added to watchlist vs. discovered via CSV). Phase D6 (vendor aliases) needs to deduplicate. Decision: do we auto-add discovered software vendors to the watchlist, or keep them separate? **Recommendation:** keep separate; surface a "promote to watchlist" action in the asset UI.
4. **No background job runner exists today beyond APScheduler.** The CSV import "background match job" (C6) can either (a) run synchronously for small uploads, (b) use a new APScheduler one-shot job, or (c) reuse the ingest pattern. Recommend (b) — schedule a one-shot run after import commits.
5. **Demo org `is_demo=true` propagation.** New tables (`assets`, `asset_software`, `scan_runs`) need fixture data for the demo org or the new dashboard tab will be empty for unauthenticated viewers. A8 covers this — don't skip it.
6. **Frontend `fetchWithAuth.ts` doesn't handle multipart uploads.** CSV upload (Phase C) needs either an extension to fetchWithAuth or a new helper. Decision required in C7.
7. **Alembic head check is strict.** v034–v041 all need to be a clean linear chain. If two devs cut migrations in parallel, the CI will fail. Recommend: one teammate owns the migration sequence and rebases incoming branches.
8. **`requirements.txt` does not currently include `pandas`.** If the CSV parser uses pandas (overkill for 10k rows; stdlib `csv` is fine), this needs explicit approval per CLAUDE.md. **Recommendation: stdlib `csv` + `pydantic` validation, no new deps.**
9. **No e2e test infra exists.** F7 (Playwright) would be the first one. If we don't want to add Playwright now, replace with a documented manual test script in `docs/manual_test_month2.md`.
10. **Sentry DSN is still not deployed.** Carried from Month 1 ops items. Doesn't block Month 2 dev, but means we'll be flying blind on staging errors until it's set.

---

## Outside-Scope / Nice-to-Haves (parking lot)

Ideas that aren't on the 6-month plan but came out of investigation. Don't ship in Month 2 unless A–F land early.

### High value, low effort
- **N1 — Sample CSV download link.** One-click download a perfectly-formatted sample file from the upload page. Reduces support tickets to zero. (~30 min.)
- **N2 — "Copy as curl" on every API call from the dashboard.** Power-user feature; helps the team debug. (~2 hr.)
- **N3 — Inventory diff between scan_runs.** "You added 3 assets and 12 software packages since last upload." Single new endpoint, simple UI card. (~half day.)
- **N4 — Weekly digest email.** "This week, 4 new KEV entries matched your inventory." Reuses existing data; no new ingestion. Needs SES/Resend (new dep — approval required).

### Medium value
- **N5 — Asset tagging.** Free-text tags on assets (`production`, `pci-zone`, `executive-laptop`). Drives prioritization. ~1 day backend + frontend.
- **N6 — CSV column auto-mapping.** Users upload CSV with non-canonical headers; we use fuzzy match to suggest mappings. Improves activation but is a rabbit hole — defer to Month 3.
- **N7 — Slack alert on new KEV match.** Per-org Slack webhook stored encrypted, fires when a new KEV match lands. Pairs naturally with N4.
- **N8 — Asset risk score = max(software CVSS) + EPSS percentile.** Trivial computation once D + C land. Surfaces "your riskiest asset is X" on the overview.
- **N9 — Import history rollback.** "Undo last upload" reverts to previous `scan_runs` state. Useful when a user uploads bad CSV.
- **N10 — Public-facing trust page improvements.** Add the new sources (assets, M365, EPSS) to the existing `/privacy` and `/data-handling` pages.

### Speculative / stretch
- **N11 — Auto-discover from primary domain.** Use existing `domain_checks.py` (HIBP/Shodan/OTX) to suggest assets based on subdomain enumeration. Already half-built; could be a Month 3 wedge.
- **N12 — Compare-against-peer dashboard.** Anonymized industry/sector comparison ("you have 3 KEV matches; median in your sector is 7"). Requires enough orgs in the system; revisit Q3.
- **N13 — CycloneDX SBOM export.** We accept SBOMs (N9 stretch on C11) — symmetrically, let users export their inventory as SBOM. Compliance teams will love it.
- **N14 — Read-only "auditor" role.** Distinct from viewer — can see everything including audit logs but cannot trigger ingest or change profile. Useful for SOC2 / pen-test reviewers.
- **N15 — IPv6 + multi-IP asset support.** Today `assets.ip_address` is a single column. Migrate to a child `asset_addresses` table if any real customer needs it.

---

## Parallelization map (Sprint 1)

```
Week 5                                Week 6
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ A1-A5  Migrations + repos       │   │ A6-A10 Tests + fixtures         │
│ B1     Intake gating audit      │   │ B2-B7  Decouple + skip buttons  │
│ D1-D3  EPSS schedule + storage  │   │ D4-D7  EPSS UI + aliases        │
│ E1-E3  M365 app reg + consent   │   │ E4-E7  Callback + sync          │
└─────────────────────────────────┘   └─────────────────────────────────┘
                                       ↓
                                  Sprint 1 demo: 
                                  - New user reaches dashboard with just domain
                                  - EPSS in NVD table
                                  - M365 spike connects in staging
```

```
Week 7                                Week 8
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ C1-C5  Upload endpoints         │   │ C6-C11 Background match + UI    │
│ E8-E9  M365 tests + docs        │   │ F1-F4  Dashboard tab + analytics│
└─────────────────────────────────┘   ┌─────────────────────────────────┐
                                       │ F5-F8  Polish + e2e smoke       │
                                       └─────────────────────────────────┘
                                       ↓
                                  Sprint 2 demo:
                                  - Full CSV upload → assets → KEV match
                                  - Activation analytics live
                                  - Trust pack refreshed
```

Different teammates can take different vertical slices: backend-heavy person on A+D, full-stack on B+F, frontend-leaning on C, and one person can own the E spike end-to-end since it's small and self-contained.

---

## Definition of done

- [ ] All migrations v034–v041 applied; Alembic single-head check green.
- [ ] CSV upload → assets in DB → KEV match visible in UI works for a fresh org.
- [ ] EPSS scores present in DB; visible in NVD table.
- [ ] M365 OAuth spike completes in staging (devices appear as assets).
- [ ] Onboarding "fast path" — new user can reach a useful dashboard with org name + domain only.
- [ ] All new endpoints registered in `data_status.py` with correct source badge.
- [ ] All new tables have org-scoped queries; no cross-org leakage in tests.
- [ ] Activation analytics flow records expected events without PII leaks.
- [ ] CI green: pytest + ruff + eslint + tsc + vitest + Alembic.
- [ ] Trust pack docs refreshed: `DATA_SOURCE_STATUS.md`, `PRODUCT_VIABILITY_ROADMAP.md`, this doc's status updated to all-checked.
- [ ] Month 1 carryover items (NVD/Census key rotation, Sentry DSN, branch protection) reviewed in standup — not blockers for Month 2 dev but raised.

---

## Open questions to resolve in week 5 kickoff

1. Do we ship Phase C6 (literal-match KEV findings on inventory) in Month 2, or wait for the Month 3 CPE matcher? *Recommendation: ship the literal match labelled "preliminary," replace in Month 3.*
2. Do we add `pandas` or stick to stdlib `csv`? *Recommendation: stdlib; no new dep needed.*
3. Do we add Playwright for F7 e2e, or document manual test? *Recommendation: manual for now; Playwright is a Month 3+ investment.*
4. Who owns the Alembic migration sequence to prevent parallel-branch conflicts?
5. Are activation analytics (F4) acceptable from a privacy standpoint? Audit against `pii_inventory.md` before merging.
