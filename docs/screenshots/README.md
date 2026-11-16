# Screenshots

The main README embeds these. They are captured from a local stack with a
synthetic organization and inventory (never a real customer org), matched
against live public CISA KEV, NVD, EPSS and IC3 data.

| File | Route | What it shows |
| --- | --- | --- |
| `dashboard.png` | `/overview` | Inventory health and vendor vulnerability alerts |
| `assets-findings.png` | `/org/assets` | Host inventory ranked by risk, KEV-matched hosts flagged |
| `vendor-prioritization.png` | `/org/vendor-alerts` | KEV entries matched to the org's technology stack, by priority |
| `remediation-plan.png` | `/org/risk` (Action plan card) | Prioritized action plan for the org's industry |
| `executive-report.png` | `/org/report` | Risk snapshot, costliest attack types, projected annual loss |

## Recapturing

1. Start the stack, run migrations and seed (see [docs/SETUP.md](../SETUP.md)).
2. Sign in, complete onboarding with a made-up organization, then:
   - upload a synthetic inventory CSV at `/org/assets/upload` (format:
     [frontend/public/sample-inventory.csv](../../frontend/public/sample-inventory.csv));
   - add vendors in Settings → Technology (`vendor_name,product_name` CSV,
     using CISA KEV's exact product names), a domain such as `example.com`,
     and answer at least one security question so the AI Briefing and report
     unlock.
3. Findings need NVD CPE data. Without an `NVD_API_KEY` the nightly CPE
   backfill is slow, so set a free key in `backend/.env` before capturing.

Keep each PNG about 1440 px wide and under 400 KB. Crop out anything that
identifies a real person or organization (the executive report header shows
the signed-in user's email).
