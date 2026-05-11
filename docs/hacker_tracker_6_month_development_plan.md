# Hacker Tracker 6-Month Development Plan

## Purpose

This document turns the repo investigation findings into an implementation roadmap for taking Hacker Tracker beyond a semester project. The plan keeps the original Cyber Security Threat Intelligence Dashboard alive while also developing the stronger pivot: a lightweight SMB vulnerability/exposure management platform with asset inventory, scanner-based visibility, CVE matching, and executive reporting.

The plan assumes one primary developer is doing most of the work, so the roadmap prioritizes features that create the most product value without requiring a full engineering team.

### Team-sizing note

Hacker Tracker has a six-person team (Ethan Gagliano, Arlo Kharod, Cody Kinney, Sean Winfield, Phat Nguyen, Darrin Rious). This roadmap is paced for **one primary developer driving the critical path** with the rest of the team contributing to parallelizable work. Suggested teammate roles, to be confirmed in Week 0:

- **Validation lead** — owns Week 0 interviews, ongoing pilot recruitment, feedback synthesis.
- **Frontend/UX** — owns onboarding simplification (Month 2), asset/findings dashboards (Month 5).
- **Scanner OS coverage** — owns one OS collector each (Months 4–5) once the skeleton exists.
- **Threat-intel dashboard polish + IC3 cleanup** (Month 1).
- **QA/testing/docs** — owns matcher regression set, multi-tenancy isolation tests, pilot docs.

If the team is unable to commit, the timeline must be extended or scope reduced — do not silently absorb the gap.

---

## Product Direction

### Current product identity

Hacker Tracker is currently strongest as a cyber threat intelligence dashboard. It aggregates and displays public security data such as NVD CVEs, CISA KEV vulnerabilities, IC3 cybercrime/economic context, anomaly signals, and executive-style reporting.

### Recommended product pivot

The strongest long-term direction is:

> Hacker Tracker helps small businesses and MSPs identify what assets/software they have, match those assets to real vulnerabilities, prioritize what matters most, and generate plain-English reports.

This does not replace the threat intelligence dashboard. Instead, the threat dashboard becomes the intelligence layer behind the more practical product.

### Final product framing

Hacker Tracker should become:

> An SMB-first vulnerability and cyber exposure dashboard that combines public threat intelligence, lightweight asset inventory, vulnerability matching, and executive reporting.

---

## Feature Ranking by Strength and Impact

Scoring:
- Impact: how much this improves real-world usefulness.
- Strength: how strongly it supports the product's viability.
- Difficulty: estimated implementation complexity for one primary developer.
- Priority: implementation priority.

| Rank | Feature | Impact | Strength | Difficulty | Priority | Why It Matters |
|---:|---|---:|---:|---:|---|---|
| 1 | Asset inventory model | 10/10 | 10/10 | Medium | Critical | Without assets/software, the product cannot know what vulnerabilities actually affect a company. |
| 2 | CSV/SBOM upload onboarding | 9/10 | 9/10 | Medium | Critical | Gives users value without forcing them to manually type everything. Also easier than building an agent first. |
| 3 | Version-aware CVE/CPE matching | 10/10 | 10/10 | High | Critical | Turns the dashboard from general information into actual vulnerability management. |
| 4 | Prioritized remediation dashboard | 9/10 | 9/10 | Medium | Critical | Shows users what to fix first instead of only showing raw CVE data. |
| 5 | Executive PDF/CSV report export | 8/10 | 9/10 | Medium | High | Especially valuable for MSPs, class demos, pilots, and business validation. |
| 6 | Reduced onboarding flow | 8/10 | 8/10 | Medium | High | Fixes the poster critique that onboarding is too painful. |
| 7 | Read-only host scanner MVP | 10/10 | 10/10 | High | High | The biggest product leap. It makes Hacker Tracker operational instead of only informational. |
| 8 | Agent upload endpoint + scan history | 9/10 | 9/10 | Medium/High | High | Needed once the scanner exists. Stores scan results and enables historical tracking. |
| 9 | Threat intel dashboard polish | 7/10 | 8/10 | Medium | High | Keeps the original product strong and makes the app feel credible. |
| 10 | IC3 hardcoded data cleanup/labeling | 7/10 | 8/10 | Low/Medium | High | Prevents fake/static data from damaging trust. |
| 11 | Data freshness / ingest status page | 7/10 | 8/10 | Medium | High | Proves which data is real, stale, failed, or demo-mode. |
| 12 | Domain intelligence checks | 7/10 | 7/10 | Medium | Medium | Quick security value if HIBP/Shodan/OTX keys are already configured. |
| 13 | MSP/client multi-tenant view | 8/10 | 9/10 | High | Medium | Strong business direction, but should come after core scanning/matching works. |
| 14 | M365/Entra connector | 8/10 | 8/10 | High | Medium | Useful but OAuth/admin permissions can consume time. Start after CSV/SBOM upload works. |
| 15 | Compliance/security-control mapping | 6/10 | 7/10 | Medium | Medium | Useful for reports but not as important as asset visibility. |
| 16 | Network scan mode | 8/10 | 8/10 | High | Later | Powerful but needs consent, scope controls, and safety guardrails. |
| 17 | Billing/self-serve SaaS setup | 5/10 | 6/10 | High | Later | Not needed until pilots prove demand. |
| 18 | Discovery interviews (Week 0 gate) | 10/10 | 10/10 | Low | Critical | Avoids spending months on a pivot the market does not want. |
| 19 | EPSS ingestion | 8/10 | 9/10 | Low/Medium | Critical | Risk scoring depends on it; currently missing from the repo. |
| 20 | Observability (Sentry, structured logs) | 8/10 | 8/10 | Low | High | Cannot debug a pilot without it. |
| 21 | CI/CD pipeline (tests, lint, migration check) | 7/10 | 8/10 | Low/Medium | High | Pays for itself by week 3; required for safe parallel work. |
| 22 | Matcher regression test set | 9/10 | 9/10 | Medium | High | One bad high-confidence match destroys trust permanently. |
| 23 | Code-signing for scanner binaries | 9/10 | 9/10 | Low (work) / High (cost) | High | SMB IT will not run an unsigned `.exe`. Required before scanner ships. |
| 24 | Agent auto-update mechanism | 8/10 | 8/10 | Medium/High | High | Cannot ask 100 admins to manually re-deploy a fixed agent. |
| 25 | Data lifecycle (org delete, export, retention) | 8/10 | 8/10 | Medium | High | Required before onboarding real customers; legal in some jurisdictions. |
| 26 | Multi-tenancy isolation testing | 9/10 | 9/10 | Medium | High | MSP path requires verified cross-org access prevention. |
| 27 | Demo mode removal (replace with seed script) | 6/10 | 7/10 | Low/Medium | High | Mixing demo + real data in production is a footgun. |
| 28 | NVD CPE cache + rate-limit-aware fetcher | 8/10 | 8/10 | Medium | High | NVD API rate limits will throttle matching jobs without it. |

---

## Key Product Principle

Do not build more dashboards before the product has real asset context.

The current dashboard can say:

> These vulnerabilities exist in the world.

The improved product should say:

> These vulnerabilities affect your environment, on these machines, and these are the top fixes.

That difference is what makes the project viable.

---

## Architecture Target

### Existing major areas

- `backend/` — FastAPI backend
- `frontend/` — React frontend
- `backend/app/api/routes/v1/` — API route layer
- `backend/app/services/` — business logic
- `backend/app/repositories/` — database access
- `backend/app/ingestors/` — NVD, CISA KEV, IC3, economic data
- `frontend/src/pages/` — page-level frontend screens

### New areas to add

```text
agent/
  README.md
  cmd/
  internal/
  collectors/
  build/
  examples/

backend/app/api/routes/v1/inventory.py
backend/app/api/routes/v1/assets.py
backend/app/api/routes/v1/agents.py            # enrollment, token rotation
backend/app/api/routes/v1/data_lifecycle.py    # export + delete
backend/app/services/inventory_service.py
backend/app/services/cpe_matcher.py
backend/app/services/cpe_cache.py              # NVD rate-limit-aware fetcher
backend/app/services/risk_scorer.py
backend/app/services/matcher_regression.py     # nightly known-good check
backend/app/services/agent_token.py            # issue/rotate/revoke
backend/app/services/forecasting.py            # vendor KEV momentum, sector trends, watchlist
backend/app/services/domain_enrichment.py      # domain -> industry/size inference
backend/app/services/report_renderer.py        # server-side PDF (replace window.print)
backend/app/repositories/assets.py
backend/app/repositories/scan_runs.py
backend/app/repositories/agent_enrollments.py
backend/app/ingestors/epss.py                  # currently missing
backend/app/api/routes/v1/forecasting.py
backend/app/api/routes/v1/reports.py
backend/app/schemas/assets.py
backend/app/schemas/inventory.py
backend/app/schemas/agent.py
backend/app/integrations/
  m365.py
  google_workspace.py
backend/app/core/observability.py              # Sentry init, request IDs
backend/tests/regression/matcher_known_good.py
.github/workflows/ci.yml                       # tests, lint, alembic check
.github/workflows/agent-release.yml            # signed binary builds

frontend/src/api/assets.ts
frontend/src/api/inventory.ts
frontend/src/api/forecasting.ts
frontend/src/pages/AssetsPage.tsx
frontend/src/pages/AssetDetailPage.tsx
frontend/src/pages/UploadInventoryPage.tsx
frontend/src/pages/ReportsPage.tsx
frontend/src/pages/ForecastingPage.tsx
frontend/src/pages/PrivacyPage.tsx
frontend/src/pages/DataHandlingPage.tsx
frontend/src/components/assets/InventoryUploadPanel.tsx
frontend/src/components/assets/AssetSoftwareTable.tsx
frontend/src/components/assets/ScanRunsTable.tsx
frontend/src/components/forecasting/VendorMomentumCard.tsx
frontend/src/components/forecasting/SectorTrendCard.tsx
frontend/src/components/forecasting/WatchlistTable.tsx
frontend/src/components/reports/ReportModeToggle.tsx

docs/PRODUCT_VIABILITY_ROADMAP.md
docs/DATA_SOURCE_STATUS.md
docs/agent_auto_update.md
docs/threat_model_tenancy.md
docs/pii_inventory.md
```

---

## Proposed Data Model

### Core tables

```text
organizations
users
organization_members
```

### New asset/inventory tables

```text
assets
- id
- org_id
- hostname
- display_name
- asset_type
- os_name
- os_version
- architecture
- source
- last_seen_at
- created_at
- updated_at

scan_runs
- id
- org_id
- asset_id
- source
- scanner_version
- status
- started_at
- completed_at
- raw_payload_hash
- created_at

asset_software
- id
- org_id
- asset_id
- scan_run_id
- name
- normalized_name
- version
- vendor
- package_manager
- install_path
- cpe_uri
- created_at

asset_ports
- id
- org_id
- asset_id
- scan_run_id
- port
- protocol
- service_name
- process_name
- exposure
- created_at

asset_services
- id
- org_id
- asset_id
- scan_run_id
- service_name
- status
- version
- created_at

asset_findings
- id
- org_id
- asset_id
- asset_software_id
- cve_id
- source
- cvss_score
- epss_score
- kev_flag
- severity
- risk_score
- match_confidence            # high | medium | low | needs_review
- status                      # open | accepted_risk | false_positive | in_progress | fixed
- false_positive_reported_by  # user feedback loop
- remediation_summary
- created_at
- updated_at

epss_scores
- cve_id (PK, FK -> cves)
- epss_score
- percentile
- as_of_date
- created_at

cpe_match_cache
- id
- cpe_uri
- cve_id
- version_start_including
- version_start_excluding
- version_end_including
- version_end_excluding
- fetched_at
- ttl_expires_at

agent_enrollments
- id
- org_id
- token_hash                  # never store raw
- token_prefix                # for UI display
- name
- scopes                      # json: which endpoints allowed
- created_by_user_id
- created_at
- last_used_at
- revoked_at
- expires_at

vendor_aliases
- id
- raw_name
- normalized_vendor
- normalized_product
- source                      # manual | nvd | curated
- confidence
- created_at

audit_log
- id
- org_id
- user_id
- action                      # upload, export, delete, token_issue, token_revoke
- resource_type
- resource_id
- ip_address
- created_at
```

### Why this matters

The current vendor-based matching is too broad. A company entering a vendor name does not prove they are affected by a specific CVE. The new asset/software model allows Hacker Tracker to match actual installed software and versions against NVD/CISA data.

---

## Six-Month Roadmap Overview

| Phase | Theme | Main Outcome |
|---|---|---|
| **Week 0** | **Validation gate** | **5–8 discovery interviews completed; written go/no-go memo on the MSP pivot. No new code on the pivot path until this passes.** |
| Month 1 | Stabilize, instrument, harden CI | Threat-intel dashboard is credible; Sentry + structured logs + CI live; data-lifecycle endpoints exist; demo mode segregated. |
| Month 2 | Reduce onboarding and add inventory upload | Users can upload CSV/SBOM-style inventory instead of manually typing everything. |
| Month 3 | EPSS ingestor + version-aware vulnerability matching + matcher regression harness | App matches inventory to CVEs/KEV with confidence levels, regression-tested against a known-good set. |
| Month 4 | Single-OS scanner MVP + agent trust model | A read-only Linux scanner uploads inventory via a hardened enrollment-token flow with auto-update design in place. |
| Month 5 | Asset dashboard, server-side PDF reports w/ evidence citations + modes, forecasting MVP, Windows scanner, multi-tenancy isolation tests | Users view assets/findings/top risks; deterministic PDFs ship in Executive/Technical/MSP-client modes; "Rising Risks" forecast endpoints live; Windows scanner shipping; cross-org access tests pass. |
| Month 6 | Pilot hardening, MSP direction, third OS (optional), backup drill | Multi-client reporting, code-signed binaries, restore-from-backup verified, pilot-ready. |

### Go/no-go gates (explicit checkpoints)

These are mandatory checkpoints. Do not pass without the criteria met. Each has explicit "stop or pivot" criteria — they exist to prevent the most expensive failure mode (building toward an invalid premise).

#### Checkpoint 1 — End of Week 0 (validation gate)

**Proceed if:**
- ≥8 interviews done; ≥6/12 ask unprompted for asset-specific vulnerability reporting
- ≥3 MSP/IT users say current reports are painful or insufficient
- ≥2 verbal pilot commitments
- CSV/SBOM or M365/GWS preferred over long manual onboarding

**Stop or pivot if:**
- Users already use Huntress/Defendify/ConnectSecure and see no gap
- SMBs say "my MSP handles that"; MSPs say "ConnectSecure already covers this"
- No pilot offers
→ Drop Months 3–6 pivot work; stay on threat-intel-dashboard polish path only.

#### Checkpoint 2 — End of Month 3 (matcher quality gate)

**Proceed if:**
- Regression set passes ≥95% on the known-good set
- High-confidence false-positive rate <2%
- ≥1 interviewee has reviewed sample findings and judged them useful

**Stop or pivot if:**
- Matcher is too noisy at any confidence tier
- Inventory upload friction is blocking real users from completing the flow
- Reports still feel generic to interview reviewers
→ Spend Month 4 hardening the matcher instead of starting the scanner.

#### Checkpoint 3 — Before scanner build (Month 4 entry gate)

**Proceed if:**
- Checkpoint 2 passed
- ≥2 real users (interviewees or prospective pilots) explicitly say they would test a read-only inventory agent
- Privacy/data-handling pages live; agent trust model documented
- Code-signing cert procurement initiated

**Stop or pivot if:**
- Users will not install a third-party agent under any conditions
- CSV/SBOM workflow alone proves to be sufficient value for pilots
- Code-signing or distribution complexity outweighs pilot demand
→ Skip scanner; reallocate Month 4 to OAuth integrations (M365/GWS) and report polish.

#### Checkpoint 4 — End of Month 5 (pilot gate)

**Proceed if:**
- ≥1 external pilot user has run the scanner end-to-end
- Reports have been sent to ≥1 actual SMB client by an MSP user
- Multi-tenancy isolation tests pass

**Stop or pivot if:**
- No pilot blocker resolution path
→ Reallocate Month 6 to whatever the pilot blocker is rather than MSP features.

---

# Week 0 — Validation Gate

## Goal

Confirm the SMB/MSP exposure-management pivot is what the market wants **before** committing 6 months of build effort. This is the cheapest way to avoid the worst possible outcome: a finished product no one needs.

## Why this comes before Month 1

The previous investigation explicitly identified "no real-world validation" as one of three structural critiques. The 6-month plan as originally written assumed the pivot was correct without testing that assumption. One week of interviews can redirect or confirm the entire roadmap.

## Workstream 0.1 — Discovery interviews

### Targets (10–15 conversations across 4 segments)

- 4 SMB owners or office managers (10–200 employees)
- 4 internal IT admins
- 4 MSP owners/technicians
- 2–3 cybersecurity consultants

### Discovery questions (ordered by signal value)

1. Walk me through how you currently learn that a vulnerability affects you.
2. What tools (paid or free) do you use for asset inventory today?
3. If a tool gave you a prioritized list of "patch these 5 things this week," would you actually act on it? Who?
4. How do you feel about installing a third-party agent on endpoints? What would it take to trust one?
5. Would you rather connect M365/Google Workspace via OAuth, or upload a CSV from existing tools?
6. (MSPs) How many clients do you report to? What does that report currently look like? What would you pay per client per month for an automated version?
7. Do you have a budget line for "vulnerability management" or "security posture"? How much?
8. Single biggest unsolved security headache right now?
9. SOC 2 / cyber insurance / compliance attestation requested in the last 12 months? What did you scramble for?
10. If we gave you a free 30-day pilot, what would success look like at day 30?
11. Who else would have to approve buying this?

### Validation signals

- **Validates pivot:** ≥6/12 ask unprompted for "show me what I have and what's vulnerable." MSPs willing to pay $5–15/endpoint/month. ≥2 verbal pilot commitments.
- **Invalidates pivot:** Most respondents already use Huntress/Defendify/Sophos and see no gap; SMBs say "my MSP handles that"; no one offers a pilot slot.

## Workstream 0.2 — Go/no-go memo

A single-page written decision: pivot or stay. If pivot: which 1–2 customer quotes anchor each Month 1–6 priority. If stay: revised plan focused on threat-intel polish only.

## Definition of done

- 8+ interviews completed with notes
- Written go/no-go memo signed by the team
- ≥2 verbal or written pilot commitments (if proceeding with pivot)
- Roadmap explicitly amended or confirmed based on findings

---

# Month 1 — Stabilize the Current Threat Intelligence Dashboard

## Goal

Make the current Hacker Tracker dashboard credible, transparent, and demo-ready before adding the pivot features.

## Why this comes first

The repo investigation found that some parts are real and wired, while others are hardcoded, stubbed, or demo-mode dependent. Before showing this to real users, the app needs to clearly separate real data from static/demo data.

## Workstream 1.1 — Data source transparency

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Add visible labels for real/static/demo data | High | Low | Dashboard components, IC3 pages, exploited vulns page |
| Add data freshness cards | High | Medium | `backend/app/workers/scheduler.py`, ingest routes, frontend dashboard |
| Show last successful NVD/KEV ingest | High | Medium | ingest service/routes |
| Show failed/stale ingestion warnings | Medium | Medium | backend ingest routes, frontend status component |
| Make `ENABLE_DEMO_MODE` visible in UI if active | High | Low | backend config, frontend banner |

### Definition of done

- User can tell what data is real, stale, static, or demo-mode.
- NVD and CISA KEV ingest status is visible.
- No static IC3 data is presented as live/fully parsed data.

## Workstream 1.2 — IC3 cleanup

### Options

Option A: Label current IC3 data as static FBI summary data.

Option B: Build real IC3 PDF/CSV parsing.

For one primary developer, choose Option A first.

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Rename hardcoded IC3 data labels to static summary | High | Low |
| Add source/year disclosure to IC3 charts | High | Low |
| Add TODO/backlog issue for real parsing | Medium | Low |
| Prevent static data from being described as live | High | Low |

### Definition of done

IC3 charts are still useful for context, but they do not pretend to be live or fully parsed.

## Workstream 1.3 — Threat dashboard polish

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add threat overview landing dashboard | High | Medium |
| Add cards for CVEs ingested, KEV count, high severity count, latest ingest | High | Medium |
| Add top exploited vendors/products section | Medium | Medium |
| Add industry/sector context from IC3 | Medium | Medium |
| Add plain-English explanation of CVSS/KEV/EPSS | Medium | Low |

### Definition of done

The current dashboard feels like a serious intelligence product, not only a class demo.

## Workstream 1.4 — Observability and CI (foundational)

### Why now

Every later month assumes you can debug a failing matcher job, reproduce a scanner upload error, or trust that a migration won't break main. Without observability and CI in Month 1, every later month accumulates incidents.

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Add Sentry (free tier) backend + frontend | Critical | Low | `backend/app/core/observability.py`, `frontend/src/main.tsx` |
| Add request IDs and structured JSON logging with `org_id`/`user_id` correlation | High | Low/Medium | `backend/app/core/middleware.py` |
| Add GitHub Actions CI: pytest, ruff/black, frontend lint+typecheck | Critical | Low | `.github/workflows/ci.yml` |
| Add Alembic migration check (no missing migrations) to CI | High | Low | `.github/workflows/ci.yml` |
| Add basic ingest-job duration/failure dashboard (can be a single internal admin route) | Medium | Medium | `backend/app/api/routes/v1/admin_metrics.py` |

### Definition of done

A backend exception in production produces a Sentry alert with org/user context. A bad PR fails CI before merge.

## Workstream 1.5 — Demo mode segregation and data lifecycle

### Why now

Two things must be true before any external user touches the app:
1. There is no global toggle that swaps real for fake data at runtime.
2. A user/org can be deleted, and their data can be exported.

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Replace `ENABLE_DEMO_MODE` global toggle with a per-org `is_demo` flag + seed script | Critical | Medium | `backend/app/core/config.py`, `backend/scripts/seed_demo_org.py` |
| Add demo-org banner in UI when viewing a demo org | High | Low | `frontend/src/components/DemoBanner.tsx` |
| Add `DELETE /api/v1/organizations/{id}` that purges all related data | Critical | Medium | `backend/app/api/routes/v1/data_lifecycle.py` |
| Add `GET /api/v1/organizations/{id}/export` (JSON dump of all org data) | High | Medium | same file |
| Document PII inventory (hostnames, IPs, emails) | High | Low | `docs/pii_inventory.md` |
| Define and document scan_run retention policy (e.g., last 12 scans/asset) | Medium | Low/Medium | `backend/app/services/retention.py` |
| Add `docs/PRODUCT_VIABILITY_ROADMAP.md` summarizing the pivot and phased plan | High | Low | new doc |
| Add `docs/DATA_SOURCE_STATUS.md` showing source-by-source implementation status (real / static / mocked / pending) | High | Low | new doc |
| Add `docs/validation_interviews.md` tracker (one row per interview: date, segment, key quotes, follow-up) | High | Low | new doc |

### Definition of done

`ENABLE_DEMO_MODE` is removed. An org can be deleted via API and its scan_runs/assets/findings are gone. An admin can export their org's data as JSON.

---

# Month 2 — Reduced Onboarding + Inventory Upload

## Goal

Fix the onboarding critique by letting users get value through a domain and an upload instead of filling out a long form.

## New onboarding target

```text
Create account
↓
Create organization
↓
Enter domain
↓
Upload inventory CSV/SBOM OR manually add software
↓
See first risk dashboard
```

## Workstream 2.1 — Collapse onboarding gates

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Review tier gating logic | High | Medium | `backend/app/services/assessment_intake.py` |
| Make Basic useful with only org/domain | High | Medium | intake service + frontend wizard |
| Move controls/compliance questions to optional refinement | High | Medium | `AssessmentIntakePage.tsx`, `OrgProfilePage.tsx` |
| Add progress indicator: Basic / Enhanced / Comprehensive | Medium | Medium | frontend profile/report pages |
| Allow users to skip non-critical fields | High | Low/Medium | frontend wizard |

### Definition of done

A new user can reach a useful dashboard without completing every question.

## Workstream 2.2 — Inventory upload MVP

### Supported first formats

Start with simple CSV. Add SBOM later.

CSV columns:

```csv
hostname,os_name,os_version,software_name,software_version,vendor,package_manager
Office-PC-01,Windows,11,Google Chrome,124.0.0,Google,winget
Office-PC-01,Windows,11,Node.js,20.11.1,OpenJS,winget
```

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add `assets` table | Critical | Medium |
| Add `scan_runs` table | Critical | Medium |
| Add `asset_software` table | Critical | Medium |
| Add CSV upload endpoint | Critical | Medium |
| Validate CSV rows and report row errors | High | Medium |
| Add upload page | High | Medium |
| Add uploaded inventory preview | High | Medium |
| Store upload as a scan run | High | Medium |

### Backend routes

```text
POST /api/v1/inventory/uploads/csv/preview     # validate + show errors before commit
POST /api/v1/inventory/uploads/csv/import      # commit
POST /api/v1/inventory/uploads/sbom/import     # CycloneDX JSON in Sprint 2; SPDX later
GET  /api/v1/assets
GET  /api/v1/assets/{asset_id}
GET  /api/v1/assets/{asset_id}/software
GET  /api/v1/inventory/scan-runs
```

### SBOM format support sequencing

| Sprint | Format | Why |
|---|---|---|
| Sprint 1 (Weeks 5–6) | Generic CSV only | Lowest friction for first user |
| Sprint 2 (Weeks 7–8) | CycloneDX JSON | Most common SBOM format; libraries exist |
| Later | SPDX, Intune CSV, Lansweeper CSV, JAMF CSV | Driven by pilot demand |

### Domain enrichment (optional, low-priority)

Add `backend/app/services/domain_enrichment.py` to infer industry/employee/revenue from a primary domain (using public sources or a paid enrichment API). This can replace several manual onboarding fields. **Only build if Week 0 interviews say onboarding friction is a real blocker** — otherwise defer.

### Definition of done

A user can upload a CSV inventory and see assets/software listed in the app.

---

# Month 3 — EPSS Ingestion + Version-Aware CVE Matching + Risk Scoring

## Goal

Make Hacker Tracker operationally useful by matching actual software inventory to vulnerabilities. **This month is harder than the original plan estimated** — CPE matching is genuinely difficult and needs the full month plus regression tooling. Do not start the scanner (Month 4) until the Month 3 go/no-go gate passes.

## Workstream 3.0 — EPSS ingestion (currently missing from the repo)

### Why first

Risk scoring (Workstream 3.2) weights EPSS "High," but the repo has no EPSS ingestor today. Add it before scoring depends on it.

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Add `backend/app/ingestors/epss.py` (FIRST.org daily CSV) | Critical | Low/Medium | new file |
| Add `epss_scores` table + Alembic migration | Critical | Low | new |
| Wire ingestor into APScheduler (daily) | High | Low | `backend/app/workers/scheduler.py` |
| Add EPSS staleness threshold to `/ingest/health` | Medium | Low | `backend/app/api/routes/v1/ingest.py` |

### Definition of done

EPSS scores update daily and are queryable per CVE.

## Workstream 3.1 — CPE/CVE matching service

### MVP approach

Do not try to perfectly solve CPE matching immediately. Start with a conservative matcher:

1. Normalize software names.
2. Match vendor/product aliases where known.
3. Use NVD CPE data where available.
4. Avoid overclaiming. Use confidence levels.
5. Show uncertain matches separately.

### Match confidence levels

```text
High confidence:
- Exact CPE match
- Exact vendor/product/version match

Medium confidence:
- Normalized software name + vendor match
- Version appears in affected range but CPE is inferred

Low confidence:
- Name-only or fuzzy match
```

### Tasks

| Task | Priority | Difficulty | Notes |
|---|---|---|---|
| Add `cpe_matcher.py` service | Critical | High | Reference `cve-bin-tool` and `vulnerablecode` before writing your own |
| Preserve CPE version segments (`versionStartIncluding`, `versionEndExcluding`, etc.) | Critical | Medium | Currently discarded in `repositories/exploited_vuln.py` |
| Add `cpe_match_cache` table + rate-limit-aware NVD fetcher | Critical | Medium | NVD API is 5 req/30s without key, 50 with — caching is mandatory |
| Add `vendor_aliases` table seeded with curated dictionary (top 200 SMB vendors) | Critical | Medium | False positives kill trust permanently |
| Add match confidence field (`high` / `medium` / `low` / `needs_review`) | Critical | Medium | UI must surface confidence prominently |
| Store CVE matches in `asset_findings` with `match_confidence` | Critical | Medium | |
| Add background job to match new scan runs | High | Medium/High | Use the existing APScheduler patterns |
| Build matcher regression test set: 50+ (vendor, product, version) → expected_cve_set known answers | Critical | Medium | `backend/tests/regression/matcher_known_good.py` |
| Add nightly CI job that runs the regression set and fails on drift | High | Low/Medium | `.github/workflows/ci.yml` |
| Add "report false positive" button on findings UI | High | Low/Medium | Feedback loop that writes to `asset_findings.false_positive_reported_by` |

### Calibration target (Month 3 go/no-go gate)

- Regression set passes ≥95%
- "High confidence" tier has <2% false-positive rate on the regression set
- "Low confidence" findings are visually de-emphasized in UI

### Definition of done

Uploaded software inventory generates vulnerability findings with confidence levels, the regression test passes the calibration target, and false-positive feedback is captured.

## Workstream 3.2 — Risk scoring

### Recommended scoring factors

| Factor | Weight |
|---|---:|
| CISA KEV listed | Very high |
| CVSS score | High |
| EPSS score | High |
| Internet-exposed service/port | High |
| Asset criticality | Medium |
| Exploit age / recency | Medium |
| Match confidence | Required modifier |

### Risk categories

```text
Critical: Fix immediately
High: Fix this week
Medium: Schedule patch
Low: Monitor
Needs Review: Possible match, verify manually
```

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add `risk_scorer.py` | Critical | Medium |
| Combine CVSS + KEV + EPSS | Critical | Medium |
| Add asset criticality field | Medium | Low |
| Add remediation summary templates | High | Medium |
| Add finding status workflow | High | Medium |

### Finding statuses

```text
open
accepted_risk
false_positive
in_progress
fixed
```

### Definition of done

The product can produce a prioritized list of vulnerabilities with clear explanation.

---

# Month 4 — Read-Only Host Scanner MVP (Linux only) + Agent Trust Model

## Goal

Ship a read-only inventory scanner for **one operating system (Linux)** plus the backend trust model that supports it. Cross-platform expansion is deferred to Month 5+.

## Scope cut from the original plan

The original plan tried to ship Windows + Linux + macOS in 4 weeks. Realistic estimates:
- Linux software collection: 1 week (`dpkg`, `rpm`, `systemctl`, `ss` are stable APIs)
- Windows software collection: 2 weeks (registry uninstall keys + `winget` + WMI fallbacks + handling 32/64-bit)
- macOS notarization + Apple Developer cert: 1 week of calendar time even if work is small
- Code-signing certificate procurement (Windows EV cert): 2–3 weeks of calendar time

Linux only in Month 4. Windows in Month 5. macOS in Month 6 if pilots demand it.

## Scanner principle

The scanner must be read-only, transparent, and privacy-safe. Every collected field must be documented in the README and shown by `--print` before any upload.

## Recommended language

Use Go for the serious scanner.

Why:
- Single static binaries
- Smaller than Python/PyInstaller
- Easier cross-platform distribution long-term
- Less likely to look suspicious than a large packed Python binary

Use Python only for a fast local prototype if you want to test commands quickly.

## Scanner MVP commands

```bash
hacker-tracker scan --print
hacker-tracker scan --output inventory.json
hacker-tracker scan --upload --api-key <enrollment_token>
hacker-tracker scan --include-ports
```

## Data collected

| Data | Include? |
|---|---|
| OS name/version | Yes |
| Hostname | Yes |
| Architecture | Yes |
| Installed software | Yes |
| Package versions | Yes |
| Running services | Yes |
| Listening ports | Optional flag |
| Local IP | Optional |
| File contents | No |
| Browser history | No |
| Credentials/secrets | No |
| Environment variables | No |
| Documents | No |

## Workstream 4.1 — Agent repo structure

```text
agent/
  README.md
  go.mod
  cmd/hacker-tracker/main.go
  internal/collectors/os.go
  internal/collectors/software_windows.go
  internal/collectors/software_linux.go
  internal/collectors/software_macos.go
  internal/collectors/ports.go
  internal/output/json.go
  internal/upload/client.go
  examples/inventory.sample.json
```

## Workstream 4.2 — OS collectors

### Windows

Start with:
- Registry uninstall keys
- `winget list` if available
- PowerShell fallback

### Linux

Start with:
- `dpkg-query` for Debian/Ubuntu
- `rpm -qa` for RHEL/Fedora
- `systemctl` services
- `ss -tulpen` or `netstat`

### macOS

Start with:
- Homebrew packages
- `/Applications`
- `system_profiler SPApplicationsDataType`

## Workstream 4.3 — Upload endpoint and agent trust model

### Routes

```text
POST   /api/v1/agents/enroll           # exchange one-time enrollment code for token
POST   /api/v1/agents/{id}/rotate      # rotate token
DELETE /api/v1/agents/{id}             # revoke
GET    /api/v1/agents                  # list agents in org with last_used_at
POST   /api/v1/inventory/scans         # scanner uploads here, agent token bearer
GET    /api/v1/inventory/scans/{scan_run_id}
```

### Trust model design (must be settled before coding)

| Question | Decision required |
|---|---|
| One token per agent or one per org? | One per agent (enables per-host revocation) |
| Token storage on backend | Hash only (`token_hash`), display prefix only |
| Token transport | `Authorization: Bearer ht_<prefix>_<secret>` over HTTPS only |
| Replay protection | Include `scan_id` (UUID) + `nonce` in payload; reject duplicates within 24h |
| Token expiry | Default 365 days; configurable per-org |
| Rotation flow | New token issued; old token valid for 24h grace |
| Conflicting hostnames | Backend uses `(org_id, agent_id)` as identity, not hostname |
| Stale agents | Mark inactive after 30 days no-contact; surface in admin UI |

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add `agent_enrollments` table + Alembic migration | Critical | Low/Medium |
| Add token issue/rotate/revoke service | Critical | Medium |
| Add agent enrollment UI in org settings | Critical | Medium |
| Add scanner upload endpoint with bearer-token auth | Critical | Medium |
| Validate scanner JSON schema (versioned) | Critical | Medium |
| Store scan as `scan_run` with replay-detection | Critical | Medium |
| Trigger CVE matching after upload | High | Medium |
| Add scanner version tracking + min-supported-version enforcement | High | Low |
| Add `audit_log` entries for enroll/rotate/revoke/upload | High | Low |
| Rate-limit upload endpoint per token | High | Medium |
| Document enrollment + revocation flow for users | High | Low |

### Definition of done

The scanner collects local Linux inventory, prints JSON, uploads it via a per-agent bearer token, and the backend turns it into assets/software/findings. Tokens can be rotated and revoked. Audit log records all enrollments and uploads.

## Workstream 4.4 — Agent auto-update design (design doc, not implementation)

### Why now

Once you ship 100 agents you cannot ask 100 admins to redeploy a fixed version manually. Auto-update is hard to retrofit; the design must exist before v1 ships.

### Design questions to answer in a doc

- Who initiates updates: agent polls, or backend push?
- Signed update manifest format
- Rollback if a new agent version crashes on startup
- Pinning a specific agent version per org (for change-control-conscious customers)
- Update channel: stable / beta

### Definition of done

A 2–3 page design doc at `docs/agent_auto_update.md` reviewed by the team. Implementation is a Month 5 or Month 6 task depending on pilot urgency.

## Workstream 4.5 — Code-signing setup (calendar-time critical path)

### Tasks

| Task | Priority | Difficulty | Notes |
|---|---|---|---|
| Procure Windows code-signing cert (EV preferred) | Critical | Low (work) / High (cost, time) | $300–500/yr; EV cert needs hardware token; 2–3 weeks calendar time |
| Procure/use Apple Developer ID ($99/yr) | High | Low | For Month 6 macOS support |
| Document signing flow in `.github/workflows/agent-release.yml` | High | Medium | Sign during release build |
| Document notarization flow (macOS) | Medium | Medium | Defer to Month 6 |

### Definition of done

The Windows code-signing cert is in hand (or in flight) by end of Month 4 so Month 5 Windows builds can ship signed.

---

# Month 5 — Asset Dashboard, Findings, and Reports

## Goal

Turn the backend capability into something useful for users, demos, and pilots.

## Workstream 5.1 — Asset dashboard

### Pages

```text
AssetsPage
- Asset count
- Last scanned
- OS distribution
- Critical findings count
- Filter by severity/status/source

AssetDetailPage
- Host details
- Installed software
- Open ports/services
- Vulnerability findings
- Remediation recommendations
```

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Build asset list page | Critical | Medium |
| Build asset detail page | Critical | Medium |
| Add findings table | Critical | Medium |
| Add severity/status filters | High | Medium |
| Add scan history | High | Medium |
| Add fix status controls | High | Medium |

### Definition of done

Users can answer:
- What machines do I have?
- What software is installed?
- What vulnerabilities affect each machine?
- What should I fix first?

## Workstream 5.2 — Executive and technical reports

### Report types

| Report | Audience | Format |
|---|---|---|
| Executive summary | Owner/manager | PDF |
| Technical remediation | IT/admin | CSV/PDF |
| MSP client report | MSP/client | PDF |
| Raw findings export | Analyst | CSV/JSON |

### Report sections

```text
1. Organization summary
2. Scan coverage
3. Top 5 urgent findings
4. Known exploited vulnerabilities
5. Internet-exposed services
6. Risk by asset
7. Risk by software/vendor
8. Recommended remediation plan
9. Data sources and limitations
```

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Add `report_renderer.py` server-side PDF service (replace `window.print()`) | Critical | Medium | new |
| Pick PDF tool: Playwright vs WeasyPrint vs ReportLab — spike a hello-world PDF first | Critical | Medium | spike doc |
| Add `POST /api/v1/reports/generate` returning a downloadable PDF | Critical | Medium | new `routes/v1/reports.py` |
| Add CSV export endpoint | High | Low/Medium | same |
| Add report preview page | Medium | Medium | `frontend/src/pages/ReportsPage.tsx` |
| Add report-mode toggle: Executive / Technical / MSP-client | High | Medium | `components/reports/ReportModeToggle.tsx` |
| Add evidence citations on every AI summary claim (link to CVE ID / KEV row / asset / control gap) | Critical | Medium | `services/ai_summary.py`, `services/executive_summary.py` |
| Add "Top 5 urgent actions" section, each with a 1-line action | High | Medium | `services/executive_summary.py` |
| Add "Why this matters to your business" section generated from org profile | High | Medium | same |
| Add limitations/data-source section + match-confidence distribution | Critical | Low | same |
| Add MSP white-label fields: client logo, color, client name templating | High | Medium | `report_renderer.py` |

### Why server-side PDF

The current [ExecutiveReportPage.tsx](frontend/src/pages/ExecutiveReportPage.tsx) relies on browser `window.print()`, which is brittle, inconsistent across browsers, and unsuitable for an MSP emailing reports to a client. Server-side rendering produces a deterministic artifact and unblocks batch generation in Month 6.

### Why evidence citations

The AI summary today produces narrative without explicit traceability. Before showing reports to real customers, every claim must cite the data row that supports it (CVE ID, KEV entry, IC3 row, control gap). Without this the report is indistinguishable from any LLM-generated text and loses credibility on first review.

### Definition of done

A user generates a deterministic PDF with three mode toggles, every claim cites underlying data, and the report can be sent to a manager, MSP client, or pilot company without further explanation.

### Report quality rules (added)

- If the matcher returns >100 findings, the executive PDF shows only the top 25 by risk score and links to a "see all" CSV.
- Every report must include a "Data Sources and Limitations" section listing data freshness per source and match-confidence distribution.
- Low-confidence findings are listed in a separate appendix, not in the main risk count.

## Workstream 5.2.5 — Forecasting / predictive MVP

### Why now

The original project proposal promised "predictive" analytics. The current app delivers descriptive trends + z-score anomaly detection only — there is no actual forecast. Either ship a real forecast (even simple) or rename the feature in marketing materials. The cheapest, most defensible option is rolling-trend signals on existing data.

### What NOT to build

- Do not start with ARIMA, Prophet, sklearn, or TensorFlow models. The data quality (especially IC3, currently annual hardcoded) does not justify it.
- Do not promise "exact prediction." Use language like trend, momentum, watchlist, estimate.

### Three forecast features to ship

| Feature | What it does | Inputs |
|---|---|---|
| **Vendor KEV momentum** | Surfaces vendors/products with rising KEV additions over rolling 30/90-day window | `kev_catalog.added_date` |
| **Sector/state risk trend** | Shows whether a sector × state risk context is rising / stable / falling | `ic3_incidents` + `economic_indicators` |
| **Watchlist** | Per-org list of (vendors in their inventory) × (rising KEV / rising EPSS / sector trend) | org `assets` joined to above |

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Add `backend/app/services/forecasting.py` | Critical | Medium | new |
| Add `GET /api/v1/forecasting/vendor-momentum` | High | Medium | new `routes/v1/forecasting.py` |
| Add `GET /api/v1/forecasting/sector-trends` | High | Medium | same |
| Add `GET /api/v1/forecasting/watchlist?org_id={id}` | High | Medium | same |
| Add forecasting components and `ForecastingPage.tsx` | High | Medium | `frontend/src/components/forecasting/`, `pages/` |
| Wire watchlist into executive report ("rising risks for your stack") | High | Low/Medium | `services/executive_summary.py` |
| Audit copy: replace "predict" with "trend/momentum/watchlist" everywhere it's not literally a forecast | High | Low | repo-wide |

### Definition of done

The dashboard surfaces a "Rising Risks" section. Every prediction-language claim either points at a real forecast endpoint or has been renamed to descriptive language. Watchlist appears in the executive report when an org has uploaded inventory.

## Workstream 5.3 — Windows scanner

Now that the Linux scanner is shipping in pilots and the agent trust model is proven, add Windows. Use Workstream 4.2 collector patterns.

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add Windows software collector (registry uninstall keys, winget, WMI fallback) | Critical | High |
| Handle 32/64-bit registry views correctly | Critical | Medium |
| Add Windows service enumeration | High | Medium |
| Build signed `.exe` in CI using Month 4 cert | Critical | Medium |
| Test on Windows 10, 11, Server 2019, Server 2022 | High | Medium |

## Workstream 5.4 — Multi-tenancy isolation tests (required before MSP path)

### Why now

Month 6 introduces the MSP/client switcher. Before that, every query must provably enforce `org_id` filtering.

### Tasks

| Task | Priority | Difficulty | Files |
|---|---|---|---|
| Audit every repository method for `org_id` filtering | Critical | Medium | `backend/app/repositories/*` |
| Add cross-org access tests: user from org A explicitly attempts every read endpoint with org B's IDs and asserts 403/404 | Critical | Medium | `backend/tests/security/test_tenancy_isolation.py` |
| Add the same for write endpoints | Critical | Medium | same file |
| Document tenancy threat model | High | Low | `docs/threat_model_tenancy.md` |
| Consider Postgres row-level security as a defense in depth | Medium | High | future |

### Definition of done

A test suite explicitly attempts cross-org access against every endpoint and all attempts are denied. Threat model documented.

---

# Month 6 — Pilot Readiness, MSP Direction, and Hardening

## Goal

Prepare the product for real-world feedback and possible pilot use.

## Workstream 6.1 — Validation and pilot readiness

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Create pilot onboarding checklist | High | Low |
| Create data-handling/privacy page | Critical | Medium |
| Create scanner transparency page | Critical | Medium |
| Add sample inventory/demo mode that is clearly labeled | High | Low |
| Write pilot feedback form | High | Low |
| Create known limitations page | High | Low |

### Definition of done

A pilot user understands what the product collects, what it does not collect, and what the results mean.

## Workstream 6.2 — MSP/client management

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Add client organization switcher | Medium | Medium/High |
| Add MSP dashboard overview | Medium | Medium |
| Add per-client risk summary | Medium | Medium |
| Add batch report generation | Medium | High |
| Add role-based access cleanup | High | Medium |

### Definition of done

The app can support the most realistic buyer: someone managing security reporting for multiple small businesses.

## Workstream 6.3 — Security hardening

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Review auth/role enforcement across all new routes | Critical | Medium |
| Add upload size limits | Critical | Low |
| Add file type validation | Critical | Low |
| Add rate limits to scanner upload endpoint | High | Medium |
| Add audit logs for uploads and report generation | High | Medium |
| Add secret scanning in CI | High | Low/Medium |
| Add dependency scanning | Medium | Medium |
| Add basic threat model document | High | Medium |

### Definition of done

The app is not enterprise-ready, but it is responsible enough to show to real users.

## Workstream 6.4 — Backup restore drill

### Why now

Render's managed Postgres has automated backups. Untested backups are not backups.

### Tasks

| Task | Priority | Difficulty |
|---|---|---|
| Document the restore procedure | Critical | Low |
| Restore a backup into a staging database and verify schema + row counts | Critical | Medium |
| Document recovery time objective (how long does a restore take?) | High | Low |
| Schedule quarterly drills | High | Low |

### Definition of done

The team has restored a backup at least once and recorded the time it took. Procedure is documented.

## Workstream 6.5 — macOS scanner (optional, only if pilots demand)

If a pilot is on macOS, ship the macOS collector + notarization. Otherwise defer to post-roadmap. See Workstream 4.2 for collector design.

---

## Recommended Weekly Schedule for One Primary Developer

### Weekly time split

| Category | Percent |
|---|---:|
| Backend/data model | 35% |
| Frontend/UI | 25% |
| Scanner/agent | 20% |
| Testing/docs | 10% |
| User validation/interviews | 10% |

### Weekly routine

```text
Monday:
- Pick 3–5 tasks for the week
- Create issues
- Define done criteria

Tuesday–Thursday:
- Implement core tasks
- Commit frequently
- Keep migrations/tests updated

Friday:
- Test full flow
- Update roadmap
- Write demo notes
- Record blockers

Weekend/extra:
- Interviews, polish, docs, cleanup
```

---

## 24-Week Detailed Implementation Plan

## Week 0: Validation gate

### Tasks

- Schedule 8–12 discovery interviews across SMBs, IT admins, MSPs, consultants.
- Conduct interviews using the question set in the Week 0 section above.
- Write a 1-page go/no-go memo.
- Secure ≥2 verbal pilot commitments if proceeding.

### Deliverable

A signed go/no-go memo. Roadmap confirmed or revised.

---

## Weeks 1–2: Dashboard cleanup, observability, and CI

### Tasks

- Add UI indicators for real/static/demo data.
- Add data freshness display for NVD and CISA KEV.
- Label IC3 as static summary data if not fully parsed.
- Add source/last-updated footers to dashboard cards.
- Replace `ENABLE_DEMO_MODE` global toggle with per-org `is_demo` flag + seed script.
- Create `/privacy` and `/data-handling` page; document PII inventory.
- **Add Sentry (backend + frontend) and structured JSON logging with request IDs.**
- **Add GitHub Actions CI: pytest, lint, typecheck, Alembic migration check.**
- **Add `DELETE /organizations/{id}` and `GET /organizations/{id}/export` endpoints.**

### Deliverable

A cleaner, instrumented threat intelligence dashboard with CI gating PRs and a working data lifecycle path.

---

## Weeks 3–4: Onboarding simplification

### Tasks

- Update assessment tier logic.
- Let users start with only organization name/domain.
- Make security controls optional after setup.
- Add onboarding progress states.
- Add route/page for uploading inventory.
- Add sample inventory CSV template download.

### Deliverable

A user can onboard in under 5 minutes.

---

## Weeks 5–6: Asset inventory database

### Tasks

- Add Alembic migration for `assets`, `scan_runs`, `asset_software`.
- Add Pydantic schemas.
- Add repositories and services.
- Add CSV upload endpoint.
- Add validation/reporting for bad rows.
- Add asset list endpoint.
- Add asset detail endpoint.

### Deliverable

Uploaded CSV inventory becomes structured assets/software in the database.

---

## Weeks 7–8: Inventory frontend

### Tasks

- Build upload inventory page.
- Build upload preview/error display.
- Build asset list page.
- Build asset detail page.
- Add navigation item for Assets.
- Add empty states and sample data guidance.

### Deliverable

Users can upload inventory and browse assets/software in the UI.

---

## Weeks 9–10: EPSS ingestion + CPE/CVE matching spike

### Tasks

- **Add `backend/app/ingestors/epss.py` and `epss_scores` table; wire into scheduler.**
- Investigate NVD CPE match feed; reference `cve-bin-tool` and `vulnerablecode`.
- Add `cpe_match_cache` table + rate-limit-aware NVD fetcher.
- Add `vendor_aliases` table seeded with curated dictionary (top 200 SMB vendors).
- Build first version of `cpe_matcher.py` preserving CPE version segments.
- Add confidence levels (`high`/`medium`/`low`/`needs_review`).
- Store preliminary findings.

### Deliverable

Software inventory generates vulnerability findings with confidence levels. EPSS available for scoring.

---

## Weeks 11–12: Risk scoring, findings dashboard, matcher regression harness

### Tasks

- Build `risk_scorer.py` combining CVSS, KEV, EPSS, match confidence, asset exposure.
- Add `asset_findings` table with `match_confidence` and false-positive feedback fields.
- Add findings endpoints.
- Build findings dashboard with confidence-aware visual hierarchy.
- Add top 5 urgent vulnerabilities widget.
- **Build matcher regression test set (50+ known-good cases).**
- **Add nightly CI job that runs the regression set and fails on drift.**
- **Add "report false positive" button on findings UI.**

### Month 3 go/no-go gate

- Regression set ≥95% pass rate.
- High-confidence false-positive rate <2%.
- If not met, spend Weeks 13–14 hardening matcher instead of starting scanner.

### Deliverable

Users see prioritized, confidence-tiered vulnerabilities with remediation suggestions. Regression test gates further releases.

---

## Weeks 13–14: Scanner prototype (Linux only) + agent trust model design

### Tasks

- Create top-level `agent/` directory (Go module).
- Build scanner skeleton.
- Implement OS/hostname collection.
- Implement Linux installed-software collection (`dpkg`, `rpm`).
- Implement systemd service enumeration.
- Implement JSON output.
- Add `--print` and `--output` commands.
- Document exactly what is collected.
- **Write agent trust model design (token storage, replay protection, rotation).**
- **Begin Windows code-signing cert procurement (calendar-time critical path).**
- **Write `docs/agent_auto_update.md` design doc.**

### Deliverable

A local Linux scanner produces an inventory JSON file. Trust model + auto-update designs reviewed.

---

## Weeks 15–16: Scanner upload + agent enrollment

### Tasks

- Add `agent_enrollments` table + service (issue/rotate/revoke).
- Add agent enrollment UI in org settings.
- Add scanner upload endpoint with bearer-token auth + replay protection.
- Add per-token rate limiting.
- Add JSON schema validation (versioned).
- Convert scanner JSON into assets/software/scan runs.
- Trigger matching after upload.
- Add `audit_log` entries for enroll/rotate/revoke/upload.
- Add scanner upload docs.

### Deliverable

Scanner output uploads via per-agent bearer token; tokens can be rotated/revoked; audit trail recorded.

---

## Weeks 17–18: Windows scanner + multi-tenancy isolation tests

### Tasks

- Add Windows software collector (registry uninstall keys + winget + WMI).
- Handle 32/64-bit registry views.
- Add Windows service enumeration.
- Add listening ports collection behind explicit flag (Linux + Windows).
- Build signed `.exe` in CI using procured code-signing cert.
- **Audit every repository method for `org_id` filtering.**
- **Add `tests/security/test_tenancy_isolation.py` covering all read + write endpoints.**
- **Document tenancy threat model.**
- Add sample outputs for Linux and Windows.
- Add release build instructions.

### Deliverable

Scanner ships signed for Linux and Windows. Cross-org access is provably blocked.

---

## Weeks 19–20: Reports + forecasting MVP

### Tasks

- Spike server-side PDF (Playwright vs WeasyPrint vs ReportLab); pick one.
- Add `report_renderer.py` and `POST /api/v1/reports/generate` returning a deterministic PDF.
- Replace `window.print()` in `ExecutiveReportPage.tsx`.
- Add report-mode toggle: Executive / Technical / MSP-client.
- Add evidence citations to every AI summary claim.
- Add "Top 5 urgent actions" + "Why this matters to your business" sections.
- Add MSP white-label fields (logo, color, client name).
- Add CSV export for raw findings.
- Include data-source limitations + match-confidence distribution in every report.
- **Add `forecasting.py` and three endpoints: vendor momentum, sector trends, watchlist.**
- **Add forecasting page + dashboard widgets ("Rising Risks").**
- **Audit copy: replace "predict" with "trend/momentum/watchlist" wherever not literal.**

### Deliverable

Deterministic PDFs ship in three modes with evidence citations; forecasting endpoints live; "Rising Risks" surfaced in the dashboard and report.

---

## Weeks 21–22: MSP/pilot workflow

### Tasks

- Add organization/client switcher if needed.
- Add client risk summary page.
- Add pilot feedback form.
- Add sample pilot script.
- Add onboarding checklist for pilot users.
- Add limitations page.

### Deliverable

The product is ready to test with a real user or MSP-style workflow.

---

## Weeks 23–24: Hardening, backup drill, final polish

### Tasks

- Review permissions on all new routes.
- Verify audit logs cover uploads, exports, deletes, token issuance/revocation.
- Add upload size limits and per-token rate limits.
- Add tests for upload/matching/scoring.
- **Restore a Render Postgres backup into staging; record recovery time; document the procedure.**
- **Verify `ENABLE_DEMO_MODE` is fully removed from the codebase.**
- **Implement agent auto-update (per the design doc) if pilot urgency requires it.**
- Update README and architecture docs.
- Create final product demo script.
- (Optional) macOS scanner + notarization if a pilot needs it.

### Deliverable

A strong prototype that can reasonably be called an MVP candidate, with verified backups, no demo-mode footguns, and agent update path proven.

---

# Implementation Plan for Repo Agent

Use the following prompt with your repo agent.

```text
You are working in the Hacker Tracker repository. Your job is to implement the 6-month product roadmap gradually and safely. Do not make large uncontrolled changes. Work in small branches and preserve the existing threat intelligence dashboard while adding the vulnerability/exposure management pivot.

Product direction:
Hacker Tracker should become an SMB-first cyber exposure platform. It should keep the existing cyber threat intelligence dashboard using NVD, CISA KEV, IC3/economic context, and anomaly data, but add practical asset inventory, inventory upload, version-aware CVE matching, scanner support, risk prioritization, and reporting.

Important current repo findings:
- Backend is FastAPI with modular routes under backend/app/api/routes/v1/.
- Existing services live under backend/app/services/.
- NVD and CISA KEV ingestion already exist.
- Current vendor-to-KEV matching exists in backend/app/services/vendor_alerts.py but is name-only and not version-aware.
- Assessment/onboarding tier logic exists in backend/app/services/assessment_intake.py.
- Frontend onboarding/profile pages include frontend/src/pages/AssessmentIntakePage.tsx and frontend/src/pages/OrgProfilePage.tsx.
- No agent/scanner exists currently.
- IC3 data appears hardcoded/static and must be labeled or replaced.
- Demo/static data must be clearly labeled.

Development rules:
1. Preserve existing working features unless explicitly replacing them.
2. Add migrations carefully.
3. Add tests for any backend service or route you create.
4. Do not overclaim vulnerability matches. Use confidence levels.
5. Do not collect secrets, documents, browser data, credentials, or personal files in the scanner.
6. Keep scanner functionality read-only.
7. Add clear documentation for every new API and data model.
8. Prefer incremental PRs.

Phase 0 (gate, before any pivot code):
1. Confirm the Week 0 go/no-go memo exists in docs/ and concludes "go." Do not start Phase 2 work until this is true.

Phase 1 tasks:
1. Audit the current dashboard and identify every place static/demo data is shown.
2. Add UI labels for real/static/demo data.
3. Add data freshness cards for NVD and CISA KEV.
4. Label IC3 data as static summary data unless real parsing is implemented.
5. Add a data-handling/privacy page.
6. Replace ENABLE_DEMO_MODE global with a per-org is_demo flag plus a seed script.
7. Add Sentry to backend and frontend, structured JSON logging with request IDs and org/user correlation.
8. Add GitHub Actions CI: pytest, ruff/black, frontend lint+typecheck, Alembic migration check.
9. Add DELETE /api/v1/organizations/{id} (purges related data) and GET /api/v1/organizations/{id}/export (JSON dump).
10. Document PII inventory at docs/pii_inventory.md.

Phase 2 tasks:
1. Simplify onboarding so org name + domain is enough to start.
2. Move security controls/compliance questions to optional refinement.
3. Add inventory upload page.
4. Add CSV template download.
5. Add backend tables: assets, scan_runs, asset_software.
6. Add CSV upload endpoint.
7. Add asset list/detail endpoints.
8. Add frontend asset list/detail pages.

Phase 3 tasks:
1. Add backend/app/ingestors/epss.py and epss_scores table; wire into scheduler.
2. Add cpe_match_cache table and a rate-limit-aware NVD CPE fetcher.
3. Add vendor_aliases table and seed with a curated dictionary.
4. Create backend/app/services/cpe_matcher.py preserving CPE version segments.
5. Create backend/app/services/risk_scorer.py.
6. Add asset_findings table with match_confidence and false-positive feedback fields.
7. Match asset_software records to NVD/CISA KEV vulnerabilities.
8. Use match confidence levels: high, medium, low, needs_review.
9. Score findings using CVSS, KEV, EPSS, asset exposure, and match confidence.
10. Build findings dashboard with confidence-aware visual hierarchy and a "report false positive" button.
11. Build matcher regression test set (50+ known-good cases) and add a nightly CI job that runs it.
12. Gate Phase 4 on regression set passing >=95% with <2% high-confidence false positives.

Phase 4 tasks (Linux only; do not attempt Windows or macOS in Phase 4):
1. Create top-level agent/ directory (Go module).
2. Build a read-only Linux scanner MVP using dpkg, rpm, systemctl, ss.
3. Implement commands:
   - hacker-tracker scan --print
   - hacker-tracker scan --output inventory.json
   - hacker-tracker scan --upload
4. Collect only OS, hostname, installed software, package versions, services, and optional listening ports.
5. Do not collect file contents, secrets, browser data, credentials, documents, or environment variables.
6. Add versioned scanner JSON schema.
7. Add agent_enrollments table; implement issue/rotate/revoke service.
8. Add backend upload endpoint with bearer-token auth, replay protection, and per-token rate limiting.
9. Convert scanner uploads into scan_runs/assets/asset_software.
10. Trigger vulnerability matching after scanner upload.
11. Add audit_log entries for enroll/rotate/revoke/upload.
12. Write docs/agent_auto_update.md design doc.
13. Begin Windows code-signing certificate procurement (long calendar lead time).

Phase 5 tasks:
1. Build Assets dashboard.
2. Build Asset detail page.
3. Build Findings dashboard.
4. Add server-side PDF (Playwright/WeasyPrint/ReportLab — pick after spike). Replace window.print().
5. Add POST /api/v1/reports/generate and report-mode toggle (Executive / Technical / MSP-client).
6. Add evidence citations on every AI summary claim (CVE ID / KEV row / asset / control gap).
7. Add "Top 5 urgent actions" and "Why this matters to your business" sections.
8. Add MSP white-label fields (logo, color, client name).
9. Add report generation outputs: executive PDF (top 25 + appendix), technical CSV, raw JSON/CSV export.
10. Include data-source limitations and match-confidence distribution in every report.
11. Add backend/app/services/forecasting.py and three endpoints: vendor momentum, sector trends, watchlist.
12. Add forecasting page and "Rising Risks" dashboard widgets; wire watchlist into the executive report.
13. Audit copy: replace "predict" with "trend/momentum/watchlist" anywhere it isn't a literal forecast.
14. Add Windows scanner with signed .exe build in CI.
15. Audit every repository for org_id filtering; add tests/security/test_tenancy_isolation.py covering all read+write endpoints.
16. Document tenancy threat model.
17. Add pilot-readiness documentation.

Phase 6 tasks:
1. Add MSP client switcher and per-client risk summary.
2. Restore a Postgres backup into staging; document recovery time.
3. Verify ENABLE_DEMO_MODE is fully removed.
4. Implement agent auto-update if pilot urgency requires it.
5. (Optional) macOS scanner + notarization if a pilot needs it.

Start by confirming the Phase 0 gate, then create a branch and implement Phase 1 only. Before coding, print a short implementation plan with files to modify and risks.
```

---

# MVP Definition

At the end of this roadmap, Hacker Tracker should be able to do the following:

1. A user creates an organization.
2. The user enters a domain.
3. The user uploads asset/software inventory or runs a scanner.
4. The backend stores assets, software, scan runs, and findings.
5. The app matches software to CVEs using version-aware logic where possible.
6. The app prioritizes findings using CVSS, KEV, EPSS, exposure, and confidence.
7. The frontend shows:
   - threat intelligence overview
   - assets
   - vulnerabilities
   - top remediation actions
   - reports
8. The user exports an executive report and a technical remediation report.
9. The app clearly labels static/demo data and limitations.

---

# What Not to Build Yet

Do not prioritize these until the core MVP works:

| Feature | Reason to delay |
|---|---|
| Billing | No validated buyers yet |
| Full SaaS self-serve onboarding | Too much polish before product proof |
| Full cloud integrations | OAuth/admin permissions can slow progress |
| AI chatbot | Not core to value |
| Heavy network scanning | Legal/safety complexity |
| SOC 2 certification | Too early, but document toward it |
| Advanced compliance mapping | Useful later, not core now |
| Mobile app | Not relevant |
| Complex ML forecasting (ARIMA / Prophet / TF) | IC3 data is hardcoded annual; ML on this data is dishonest. Ship rolling-trend "momentum/watchlist" first. |
| Network scanning by default in agent | Legal/scope risk; opt-in flag only |
| Heavy LLM prompt engineering | Evidence citations and report modes deliver more value than better prompts |
| Public marketing site / SEO | Distracts from validation; pilots come from direct outreach |

---

# Backlog (Cross-Phase, Prioritized)

This consolidates the cross-cutting work referenced throughout the plan into one table for triage. Items repeat the per-month detail intentionally — this is the at-a-glance backlog.

## High priority

| Task | Area | Impact | Difficulty | Phase |
|---|---|---:|---:|---|
| Run Week 0 discovery interviews + go/no-go memo | Validation | Very High | Low | Week 0 |
| Label IC3/static/demo data clearly | Trust | High | Low | Month 1 |
| Add Sentry + structured logging + request IDs | Observability | High | Low | Month 1 |
| Add CI: pytest, lint, typecheck, Alembic migration check | Eng productivity | High | Low | Month 1 |
| Add `DELETE` and `GET .../export` for organizations | Data lifecycle | High | Medium | Month 1 |
| Add `docs/PRODUCT_VIABILITY_ROADMAP.md` and `docs/DATA_SOURCE_STATUS.md` | Trust | High | Low | Month 1 |
| Simplify onboarding tier logic | UX | High | Medium | Month 2 |
| Add asset inventory tables (`assets`, `asset_software`, `scan_runs`) | Core product | Very High | Medium | Month 2 |
| Add CSV inventory upload (preview + import) | Core product | Very High | Medium | Month 2 |
| Add asset list + detail pages | Core product | High | Medium | Month 2 |
| Add EPSS ingestor | Matching | High | Low/Medium | Month 3 |
| Add CPE matcher + cache + alias dictionary | Matching | Very High | High | Month 3 |
| Add risk_scorer.py | Findings | Very High | Medium | Month 3 |
| Add matcher regression test set + nightly CI run | Trust | Very High | Medium | Month 3 |
| Add server-side PDF + report mode toggle + evidence citations | Reporting | Very High | Medium | Month 5 |
| Add forecasting.py (vendor momentum, sector trends, watchlist) | Predictive | High | Medium | Month 5 |
| Multi-tenancy isolation tests | Security | Very High | Medium | Month 5 |

## Medium priority

| Task | Area | Impact | Difficulty | Phase |
|---|---|---:|---:|---|
| Add CycloneDX SBOM import | Inventory | High | Medium | Month 2 (Sprint 2) |
| Add domain enrichment service | Onboarding | Medium | Medium | Month 2 (optional) |
| M365/Entra OAuth connector | Integrations | High | High | Month 5–6 (deferred) |
| Google Workspace connector | Integrations | Medium | High | Post-roadmap |
| Add MSP/client report mode | MSP | High | Medium | Month 5 |
| Add remediation status workflow (open/accepted/fixed/etc.) | Workflow | Medium | Medium | Month 3 (table) / Month 5 (UI) |
| Add agent auto-update implementation | Agent | High | Medium/High | Month 6 |
| Add per-org rate limits and upload size limits | Security | High | Low/Medium | Month 6 |

## Low priority — defer until validated

| Task | Why delay |
|---|---|
| Network scanning in agent | Legal/scope; opt-in flag only |
| Complex ML forecasting (ARIMA / Prophet / TF) | Data quality doesn't support it; ship trend/momentum first |
| Billing / self-serve signup | Need pilots first |
| SOC 2 Type 1 | Start motion in Month 6, certification later |
| macOS scanner + notarization | Only if a pilot demands it |
| Public marketing site / SEO | Distracts from validation |

---

# Success Metrics

## Technical metrics

| Metric | Target |
|---|---|
| CSV upload success rate | 95%+ for valid template |
| Scanner JSON validation | 100% schema validation |
| Asset list load time | Under 2 seconds for small org |
| Finding generation | Under 1 minute for small upload |
| False high-confidence matches | As low as possible; manually review |
| Data freshness visibility | Always visible |

## Product metrics

| Metric | Target |
|---|---|
| Time to first useful dashboard | Under 5 minutes |
| User can identify top 5 risks | Yes |
| User can export report | Yes |
| Pilot user understands what data is collected | Yes |
| MSP/IT user says report is useful | At least 2–3 positive validations |

---

# Honest Risk Assessment

## Biggest risks

| Risk | Severity | Mitigation |
|---|---|---|
| CVE/CPE matching is inaccurate | High | Use confidence levels and do not overclaim. |
| Scanner is not trusted | High | Make it open, read-only, documented, and transparent. |
| Solo development scope is too large | High | Build CSV upload before scanner. |
| Existing dashboard still looks like a class demo | Medium | Clean up data labels and polish dashboard first. |
| No one wants to pilot | High | Interview before overbuilding. |
| IC3 data appears fake/hardcoded | Medium/High | Label or replace. |
| OAuth integrations take too long | Medium | Delay M365 until after CSV/scanner flow works. |
| Pivot is wrong and 6 months is wasted | High | Week 0 validation gate; go/no-go memo before any pivot code. |
| 6-person team contributes unevenly | High | Assign explicit owners in Week 0; do not silently absorb gaps. |
| CPE matching produces false positives that destroy trust | High | Regression test set, confidence levels, false-positive feedback loop, conservative defaults. |
| NVD API rate limits throttle matching jobs | Medium | `cpe_match_cache` + rate-limit-aware fetcher; consider getting an NVD API key. |
| Cross-org data leak in MSP path | Critical | Mandatory tenancy isolation test suite before Month 6. |
| Agent ships unsigned and SMB IT refuses to run it | High | Procure code-signing cert in Month 4 (long calendar lead time). |
| Cannot push fixes to deployed agents | High | Auto-update design doc in Month 4; implement before fleet >10. |
| Untested backups fail in a real incident | Medium | Quarterly restore drill, starting Month 6. |
| Production debugging is blind | Medium | Sentry + structured logging in Month 1 (foundational). |

---

# Best Next Step

Start with this sequence:

0. **Run Week 0 validation interviews and write the go/no-go memo. Do not write pivot code until this passes.**
1. Clean up and label the current dashboard; add Sentry, CI, data-lifecycle endpoints, and segregate demo mode.
2. Simplify onboarding.
3. Add CSV inventory upload.
4. Add asset/software database tables.
5. Add basic asset pages.
6. Add EPSS ingestor, version-aware matching, matcher regression harness.
7. Add risk scoring.
8. Add reports.
9. Build Linux scanner + agent trust model + procure code-signing cert.
10. Add Windows scanner + multi-tenancy isolation tests.
11. Pilot with real users.

The two most important near-term milestones are:

> **Week 0:** A signed go/no-go memo backed by ≥8 interviews and ≥2 verbal pilot commitments.
>
> **Week 12 (Month 3 gate):** A user can upload a software inventory CSV and receive a prioritized vulnerability report whose matcher passes the regression set at ≥95% with <2% high-confidence false positives.

The first proves the pivot is wanted. The second proves the pivot is technically defensible. Either failing kills the scanner build before it starts.
