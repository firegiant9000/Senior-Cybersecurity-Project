# Manual end-to-end smoke test — Month 2 (Phase F7)

We do not yet ship a Playwright suite (see Open Question #3 in
[month_2_execution_plan.md](month_2_execution_plan.md)). Until that
investment, the Month 2 Definition-of-Done item "CSV upload → assets in
DB → KEV match visible in UI" is verified manually using this script.

Run before tagging a Month 2 release candidate. Capture screenshots at
each numbered step for the trust pack.

## Prereqs

- Local stack running: `make up` (postgres + backend + frontend).
- Browser pointed at the local frontend (default http://localhost:5173).
- A throw-away Firebase account you can sign up with (or use staging).
- `frontend/public/sample-inventory.csv` available — the upload page
  links to it from the Drag-drop zone.

## Steps

1. **Fresh signup.** Open the app in an incognito window. Sign up with a
   new email. Land on `/onboarding`. Confirm the wizard does **not**
   force every step before the dashboard renders.

2. **Fast path.** On step 1, fill `Organization name` and `Primary
   domain` only. Click **Skip for now**. Confirm:
   - You are redirected to `/dashboard`.
   - The dashboard renders with real KEV / NVD widgets, not a wall.
   - The "Inventory Health" card on the overview shows
     `0 assets · No inventory uploaded yet.`
   - Network tab: a `POST /api/v1/analytics/events` fires with
     `event_type=intake_step_skipped` (200).
   - A separate event fires with `event_type=dashboard_first_view`.

3. **Inventory CSV preview.** From the Inventory Health card, click
   **Upload CSV →**. Drop the sample CSV into the drop zone. Click
   **Preview**. Confirm:
   - Summary shows the expected `valid_rows` and `would_create` counts.
   - No DB writes (check `assets` table is still empty).

4. **Inventory CSV import.** Click **Import**. Confirm:
   - Network: `POST /api/v1/organizations/{id}/inventory/uploads/csv/import?confirm=true`
     returns a `scan_run` with `status=running`, then a follow-up poll
     transitions to `status=succeeded`.
   - A `POST /api/v1/analytics/events` fires with
     `event_type=csv_upload_started`, then again with
     `event_type=csv_upload_completed` after success.
   - The success card shows a non-zero "KEV matches (preliminary literal
     match)" value (the sample CSV is curated to include at least one).

5. **Assets tab.** Click **View assets →** or pick the new **Assets**
   tab in the dashboard tab bar. Confirm:
   - Assets table populated with uploaded hosts.
   - Source column shows the `CSV` badge.
   - The KEV-matches column shows a non-zero count for at least one row.
   - The "KEV matches only" filter works.

6. **Drill-down.** Click **View** on a row with a non-zero KEV count.
   Confirm the modal shows:
   - CVE matches table at the top (KEV badge visible on at least one
     row).
   - Software list below it.
   - Phase-F2 disclaimer note about literal vendor+product matching.

7. **Inventory Health refresh.** Go back to the overview tab. Confirm
   the Inventory Health card now shows non-zero `Assets`, `With
   software`, and `KEV matches`, plus a relative `Last upload: …`
   timestamp and the `csv_upload` source label.

8. **Cross-org isolation (smoke).** Sign in as a different user/org.
   Confirm none of the assets from the first org appear. Sign out.

## What to capture

- Screenshot after step 2 (fresh dashboard, no inventory).
- Screenshot after step 4 (success card with KEV match count).
- Screenshot of the drill-down modal at step 6.
- Screenshot of the Inventory Health card at step 7.

These four images go into the trust pack alongside the Month 1
screenshots.

## When this test should fail

- Inventory Health endpoint returns 5xx → almost certainly a missing
  migration. Run `make migrate` and confirm `assets`, `asset_software`,
  `scan_runs`, `activation_events` exist (v034–v039).
- `dashboard_first_view` fires twice in one session → check that the
  `sessionStorage` guard in `Dashboard.tsx` is still in place.
- Analytics POSTs return 4xx with `Unknown event_type` → an event name
  was renamed on the client but not added to `ALLOWED_EVENT_TYPES` in
  `backend/app/api/routes/v1/analytics.py`.
