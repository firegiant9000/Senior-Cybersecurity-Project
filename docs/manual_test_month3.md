# Manual end-to-end smoke test — Month 3 (version-aware matching)

Mirrors [manual_test_month2.md](manual_test_month2.md). Until a Playwright suite
exists, the Month 3 Definition-of-Done — "uploaded inventory → version-aware
findings with confidence + risk tier → reviewer can flag false positives" — is
verified manually with this script. Run before tagging a Month 3 release
candidate; capture screenshots at each numbered step for the trust pack.

## Prereqs

- Local stack running: `make up` (postgres + backend + frontend).
- NVD CPE criteria present. New CVEs get criteria inline on ingest; for the
  pre-existing corpus run the backfill once (see step 1).
- `frontend/public/sample-inventory.csv` available (curated to include at least
  one version that falls inside a KEV/NVD affected range — e.g. a vulnerable
  Log4j or OpenSSL version).
- An admin Firebase account.

## Steps

1. **Seed CPE criteria for the existing corpus.** As an admin, call
   `POST /api/v1/ingest/cpe-backfill`. Confirm:
   - Response `status=started`.
   - Re-invoke until a run reports `persisted=0` in the logs (bounded per run by
     `NVD_CPE_BACKFILL_MAX_PER_RUN`). Backend log line `CPE backfill complete`
     shows `checked/persisted/criteria` counts.
   - `cve_cpe_match` now has rows: `SELECT count(*) FROM cve_cpe_match;` > 0.
   - The nightly sweep (`NVD_CPE_BACKFILL_SCHEDULE`, default `0 4 * * *`) keeps it
     fresh thereafter — no manual rerun needed in steady state.

2. **Upload inventory.** Follow Month 2 steps 3–4 to import the sample CSV.
   Confirm the `scan_run` reaches `status=succeeded`.

3. **Matcher auto-runs.** Without clicking anything, confirm a background match
   fired on import (backend log `Matcher run complete` with the org id). Open the
   **Assets** tab → **View** an affected host.

4. **Findings: confidence + risk.** In the drill-down findings table confirm:
   - A **Confidence** chip per finding. `high`/`medium` render prominent;
     `low`/`needs_review` are visually de-emphasized (muted, dashed, row dimmed).
   - A **Risk** tier chip (`Critical|High|Medium|Low|Needs Review`).
   - A KEV finding with an in-range version shows `high` confidence + a top risk
     tier; an out-of-range version for the same product produces **no** finding
     (version-aware, not name-only).
   - The **Remediation** section lists summaries for findings that have them.

5. **False-positive feedback.** Click **Report false positive** on one finding.
   Confirm:
   - Network: `PATCH /api/v1/organizations/{org}/assets/{id}/findings/{fid}/status`
     with body `{"status":"false_positive"}` returns 200.
   - The row flips to the false-positive treatment; an **Undo** affordance shows.
   - DB: that `asset_findings` row has `status='false_positive'` and
     `false_positive_reported_by` = your user id.

6. **Status survives recompute.** Re-run the matcher (`?refresh=true` on the
   findings call, or re-upload). Confirm the finding you flagged **keeps**
   `status=false_positive` (reviewer state is preserved across recompute; only
   the computed fields refresh).

7. **M365 device persistence (#124, if `ENABLE_M365_INTEGRATION=true`).** Connect
   a test M365 tenant, then `POST /api/v1/integrations/m365/sync`. Confirm:
   - Response includes a non-null `scan_run_id`.
   - **Assets** tab shows the synced devices with an `M365` source.
   - A `scan_runs` row exists with `source='m365'`, `status='succeeded'`.

8. **Regression gate (CI mirror).** `cd backend && pytest tests/regression/` —
   confirm the calibration gate passes (≥95% pass, <2% high-confidence FP). The
   nightly `matcher-regression` workflow runs the same suite.

## Pass criteria

- Findings are version-aware (in-range matches appear, out-of-range do not).
- Confidence + risk tiers render and de-emphasize low-trust matches.
- False-positive flag persists across a matcher recompute.
- M365 sync (when enabled) lands assets + a scan_run.
