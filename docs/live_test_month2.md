# Live-website test plan — Month 2

Production walkthrough for the Month 2 release (PR #165). Run after each
deploy to Firebase Hosting + Render to confirm the onboarding collapse,
CSV inventory pipeline, EPSS surface, and M365 spike all behave on the
real stack. The local-only variant is in
[manual_test_month2.md](manual_test_month2.md); this one assumes you
cannot reach `psql` or `make`, so every check is reachable from the
browser or the `gh`/`curl` CLI.

## Environments

| Surface | URL |
|---|---|
| Frontend (Firebase Hosting) | `https://hacker-tracker-75f91.web.app` |
| Backend (Render) | `https://hacker-tracker-backend.onrender.com` |
| Backend health | `https://hacker-tracker-backend.onrender.com/health` |
| Backend OpenAPI | `https://hacker-tracker-backend.onrender.com/docs` (auth-gated) |

Sentry, if configured, surfaces backend + frontend exceptions to the
project's Sentry org — check it in parallel with each step.

## Prerequisites

- A throw-away Gmail account for Firebase Auth (do **not** use a
  personal account that has been used against another org in this
  environment).
- A throw-away domain string you control on paper, e.g.
  `livetest-{YYYYMMDD}-{initials}.example.com`. Do not use a real
  customer domain.
- The sample CSV from the deployed frontend:
  `https://hacker-tracker-75f91.web.app/sample-inventory.csv`. It is
  curated to include at least one KEV-listed vendor/product so the
  preliminary-match step has something to show.
- Browser with DevTools open. Use Chrome/Edge for the Application →
  Storage panel later (cleanup step).
- Optional: `gh auth status` green, so you can write the test result
  back to the PR or a release issue.

## Pre-flight (do this before involving a teammate)

1. Hit `https://hacker-tracker-backend.onrender.com/health`. Expect
   `{"status":"ok"}` 200. Render free-tier cold-starts can take
   ~30 seconds — if you see a 503, wait and retry once before raising
   it as a finding.
2. Hit `https://hacker-tracker-75f91.web.app`. Confirm the landing
   page renders and the build hash in the page footer matches the
   commit you expect (open DevTools → Network → `index.html` →
   `etag`).
3. From DevTools Network tab, refresh once and check
   `/api/v1/data-status` is 200 and lists `epss`, `assets_inventory`,
   `asset_software`, `scan_runs`, `asset_kev_matches`, `vendor_aliases`
   alongside the Month 1 sources. If any of those are missing the
   backend deploy didn't pick up the Month 2 commits — stop and
   confirm Render redeployed.

## Steps

Capture screenshots at each numbered step; they go into the release
note.

### 1 — Fresh signup (Phase B — onboarding collapse)

1. Open the live frontend in an incognito window. Sign up with the
   throw-away Gmail account.
2. You should land on `/onboarding`. Confirm the wizard does **not**
   force every step before the dashboard renders.
3. Fill `Organization name` and `Primary domain` only (use the
   throw-away domain). Click **Skip for now** on the next step.
4. Confirm in the browser:
   - You are redirected to `/dashboard` (not blocked on the wizard).
   - The dashboard renders real KEV / NVD widgets, not a wall.
   - The Inventory Health card on the overview shows
     `0 assets · No inventory uploaded yet.`
   - The NextStepsCard renders three actions: **Upload CSV**,
     **Connect M365**, **Complete profile**.
5. Confirm in the Network tab:
   - `POST /api/v1/analytics/events` fires with
     `event_type=intake_step_skipped` (200).
   - A separate event fires with `event_type=dashboard_first_view`.
   - The skipped step is also persisted on the org — `GET
     /api/v1/organizations/{id}` (visible in the network tab as a
     side effect of the dashboard load) has a non-empty
     `intake_skipped_steps` array. **Sign out and back in.** Confirm
     the wizard does not re-pop the skipped step (R9 mitigation).

### 2 — EPSS surface (Phase D)

1. Navigate to **NVD** in the tab bar.
2. Confirm the table has an **Exploitability** column.
3. Hover the column header — the tooltip should explain the EPSS
   30-day-probability score.
4. Sort by Exploitability. The top row should have a numeric
   percentile, not `—`.
5. If every row is `—`, the EPSS job hasn't run yet on this Render
   instance (cron is daily at 02:00 UTC). Trigger it manually via the
   Pipeline Health tab → **Run EPSS now**. Wait ~60 seconds, refresh
   the NVD table.

### 3 — CSV inventory preview (Phase C)

1. From the Inventory Health card, click **Upload CSV →**.
2. Download the sample CSV link on the upload page. Drag it into the
   drop zone.
3. Click **Preview**.
4. Confirm:
   - Summary shows the expected `valid_rows` and `would_create`
     counts.
   - No request to `/import` has fired yet (Network tab).

### 4 — CSV import (Phase C + C6)

1. Click **Import**.
2. Confirm in the Network tab:
   - `POST .../inventory/uploads/csv/import?confirm=true` returns 200
     with `scan_run_id`.
   - A follow-up `GET .../scan-runs/{id}` poll transitions
     `running → succeeded` within ~30 seconds.
   - `POST /api/v1/analytics/events` fires with
     `event_type=csv_upload_started`, then with
     `event_type=csv_upload_completed` after success.
3. The success card shows a non-zero
   **"KEV matches (preliminary literal match)"** value. The sample
   CSV is curated so this must be > 0 — if it shows 0, the KEV
   ingest may be stale; check the freshness card.

### 5 — Assets tab + drill-down (Phase F1/F2)

1. Click **View assets →** or pick **Assets** in the tab bar.
2. Confirm:
   - The table shows the uploaded hostnames.
   - The Source column shows the `CSV` badge.
   - The KEV-matches column has a non-zero count for at least one
     row.
   - Toggle the **KEV matches only** filter — non-matching rows
     disappear.
3. Click **View** on a row with a non-zero KEV count.
4. The drill-down modal shows: CVE matches table at the top (KEV
   badge visible on at least one row), software list below, and a
   "preliminary literal-match" disclaimer.

### 6 — Inventory Health refresh (Phase F3)

Back on the Overview tab, the Inventory Health card now shows
non-zero `Assets`, `With software`, and `KEV matches`, plus a
relative `Last upload: …` timestamp and the `csv_upload` source
label.

### 7 — M365 OAuth (Phase E — only if feature flag enabled)

If `ENABLE_M365_INTEGRATION=true` is set on the live backend:

1. Visit **Integrations** in the tab bar.
2. Click **Connect Microsoft 365**.
3. Confirm the Microsoft consent screen lists exactly:
   `Device.Read.All`, `DeviceManagementManagedDevices.Read.All`,
   `User.Read`. Approve with the test tenant.
4. Confirm the callback lands back on `/integrations` with the card
   flipped to **Connected**.
5. Click **Sync now**. A new `scan_runs` row should appear in the
   upload-history list with `discovered_via=m365`.
6. Re-check the Assets tab — devices from the test tenant render
   alongside the CSV-uploaded ones.

If the flag is **off**, the Integrations page should show the M365
card disabled with a "coming soon" treatment. **Confirm there is no
way for a user to call `/integrations/m365/consent` from the live
UI** — the button must be disabled.

### 8 — Cross-org isolation (smoke)

1. In a different incognito window, sign up with a second throw-away
   Gmail account. Create a separate org.
2. Confirm none of the assets, scan_runs, or analytics events from
   org #1 are visible.
3. Specifically check `/api/v1/organizations/{id}/assets` in the
   Network tab — the response must be scoped to org #2 only.

## Observability checks (parallel to the steps above)

- **Sentry — backend.** No new error events should appear in the
  project's Sentry feed during the run. Authentication, validation
  4xx, and rate-limit responses are not errors and should not fire.
- **Sentry — frontend.** Same check on the frontend project. A flood
  of "ResizeObserver loop limit" warnings is benign; anything else
  needs triage.
- **Render logs.** Logs should carry `request_id`, `org_id`, and
  `user_id` JSON fields for each request. If any line is missing
  `request_id`, the Month 1 middleware regressed and needs a fix
  before claiming the deploy is healthy.

## Cleanup (do not skip)

The throw-away orgs you created above have a real domain and real
inventory rows. Leave nothing behind.

1. Sign in as each throw-away user.
2. Settings → **Delete organization**. Confirm the audit-log entry
   in the Pipeline Health view records the deletion (Month 1 C2).
3. If you cannot reach the Delete UI for any reason, fall back to
   the API:
   ```bash
   curl -X DELETE \
     -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
     https://hacker-tracker-backend.onrender.com/api/v1/organizations/{id}
   ```
4. Sign out of every incognito window. Clear `localStorage` and
   `sessionStorage` via DevTools → Application → Storage so the
   Firebase ID token does not linger on the test machine.
5. In the Firebase Auth console, delete the throw-away user records.
   Do **not** rely on the backend delete to remove the Firebase
   identity — they are separate systems.

## What to capture

- Screenshot after step 1 (fresh dashboard with NextStepsCard, no
  inventory).
- Screenshot after step 4 (success card showing KEV match count).
- Screenshot of the drill-down modal at step 5.
- Screenshot of the Inventory Health card at step 6.
- Screenshot of the consent screen at step 7 (if M365 flag is on).

Attach the four/five screenshots to the deploy issue or the PR that
triggered the deploy.

## When this test should fail (and what it means)

| Symptom | Likely cause |
|---|---|
| `/health` 503 after multiple retries | Render service unhealthy or restarting — check Render logs and Postgres status. |
| `/api/v1/data-status` missing the Month 2 keys | Render didn't redeploy the Month 2 commits — check the Render deploy log. |
| `POST /analytics/events` returns 400 `Unknown event_type` | Frontend emitted a new event the backend allowlist doesn't know about. Update `ALLOWED_EVENT_TYPES` in `backend/app/api/routes/v1/analytics.py`. |
| `dashboard_first_view` fires more than once per session | `sessionStorage` guard regressed in `Dashboard.tsx`. |
| EPSS column all `—` after a manual trigger + 60s wait | Either the scheduler isn't picking up `INGEST_SCHEDULE_EPSS`, or the upstream FIRST.org API is down. Check `/api/v1/ingest/freshness?source=epss`. |
| Inventory Health endpoint returns 5xx | Most likely a missing migration in the deploy — check Render's `predeploy` log for `alembic upgrade head` output. Confirm migrations 034 → 044 all applied. |
| CSV import 5xxs with an integrity-error trace | The `(org_id, hostname)` upsert raced with a second concurrent upload — confirm the advisory-lock code path is in the running build. |
| M365 consent loops back to the consent screen | Redirect URI mismatch between Azure AD app registration and the `M365_REDIRECT_URI` env on Render. Compare both. |
| Sentry receives a flood of duplicate events | The PII scrubber's `before_send` returned `None` for too many events — check the scrubber rules in `core/observability.py`. |
| Cross-org isolation check returns data from org #1 in org #2 | **Severity: critical.** Stop the test, file an issue, do not deploy further until the offending repository query is fixed. |

## When to repeat this test

- Before tagging a Month 2 release candidate.
- After any change to `backend/app/repositories/assets.py`,
  `asset_software.py`, `scan_runs.py`, or `services/inventory_import.py`.
- After any migration lands on `main`.
- Before a pilot demo, regardless of whether code changed.
