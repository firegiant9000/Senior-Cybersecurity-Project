# Month 1 & 2 — Operational Closeout Checklist

> **Status 2026-09-29: HISTORICAL.** Any unchecked item below that concerns pilots, staging walk-throughs for customers or commercial readiness is CANCELLED. Items about secrets and GitHub settings are superseded by S2 (SHA-pinned actions, workflow permissions, scanning gates) in [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md).

**Purpose:** Everything left to clear out Month 1 and Month 2 that is **not** code and **not** the Month 2 PR merge. These are human/ops/verification tasks — keys, secrets, GitHub settings, and staging walk-throughs. The code is already written and verified.

**Created:** 2026-06-04
**Owner key:** 👤 = project owner (needs provider/dashboard access) · 🧑‍💻 = any dev · 👥 = whole team

---

## TL;DR — do these in order

1. 🔴 **Rotate the leaked NVD + Census API keys** (blocks pilots). — Section 1
2. 🟠 **Deploy Sentry DSN secrets** so error tracking actually works. — Section 2
3. 🟠 **Turn on branch protection for `main`.** — Section 3
4. 🟡 **Run staging verification** (data-lifecycle test + manual walk-through). — Section 4
5. 🟡 **Verify the Month 2 runtime behaviors** (CSV→KEV, EPSS run, M365 OAuth). — Section 5
6. 🟢 **Add a secret-scan guard** so the key leak can't happen again. — Section 6

Priority: 🔴 critical / blocker · 🟠 high · 🟡 verification · 🟢 hardening

> ⚠️ **Bug found & fixed during verification (2026-06-04):** [backend/app/api/routes/v1/__init__.py](../backend/app/api/routes/v1/__init__.py) had a stray `ey` typed into the import block (`ey    analytics,`) — a `SyntaxError` that broke the **entire backend import** (no route could load). This was the uncommitted change in git status. Fixed; full backend suite now passes (537 passed, 1 skipped). **This fix is uncommitted — commit it before merging Month 2.**

---

## Section 1 — 🔴 Rotate the leaked API keys (pilot blocker) — ✅ DONE (2026-06-04)

> New NVD + Census keys added in the Render dashboard, and both vars are now declared in [render.yaml](../render.yaml) (`sync: false`) so the blueprint documents them. Remaining provider-side step if not already done: confirm NIST has revoked the old NVD key.

**Why this matters:** Real NVD and US Census API keys were committed to the repo and still exist in git history. Anyone with repo (or fork/mirror) access can pull them out. Until rotated, the plan says **do not start production pilots**. Scrubbing the docs (already done) does NOT fix this — the providers must issue new keys and kill the old ones.

### 1.1 — Request a new NVD key 👤
- Go to <https://nvd.nist.gov/developers/request-an-api-key>
- Request a new key (arrives by email).

### 1.2 — Revoke the old NVD key 👤
- NIST has **no self-service revoke**. Email **nvd@nist.gov** and ask them to revoke the compromised key.
- Include: the **compromised UUID** and the **public commit SHA** where it leaked, so they can prioritize.

### 1.3 — Request a new Census key 👤
- Go to <https://api.census.gov/data/key_signup.html>
- Census also has **no self-service revoke** — just request a new key and document the old one as compromised internally.

### 1.4 — Update the keys everywhere 👤 / 👥
- **Render (production backend):** Render dashboard → backend service → **Environment** → set `NVD_API_KEY` and `CENSUS_API_KEY` to the new values → save (this triggers a redeploy).
- **Every developer's local `backend/.env`:** post the new values in the team channel and have everyone update. ⚠️ The old keys keep "working" until NIST/Census action the revocation, so silent reuse is a real risk — confirm everyone switched.

### 1.5 — (Optional) Scrub git history 👤
- Only worth it **if the repo is private**. If it's public, the keys are already scraped — rotation is the only thing that matters.
- If you do it: use `git filter-repo`, and **coordinate the force-push with the whole team** (everyone re-clones).

**✅ Done when:** new keys are live in Render + every local `.env`; NIST has confirmed the old key is revoked; old Census key is replaced.

---

## Section 2 — 🟠 Deploy Sentry so observability is real — ✅ wiring verified (2026-06-04)

> **Verified in code/config this session:**
> - **Frontend:** `VITE_SENTRY_DSN` is wired into both the PR-preview and `main` deploy builds in [.github/workflows/ci.yml](../.github/workflows/ci.yml#L184) (lines 184, 229). Source-map upload is gated on `SENTRY_AUTH_TOKEN` + `SENTRY_ORG` + `SENTRY_PROJECT` (lines 234–254) — present ⇒ upload runs, absent ⇒ warns and skips. Wiring is correct; just needs the four GitHub Actions secrets set.
> - **Backend:** `SENTRY_DSN` is read from the **Render environment** (via `settings.SENTRY_DSN`, [observability.py:92](../backend/app/core/observability.py#L92)), **not** GitHub Actions — the `deploy-backend` job only pings Render's deploy hook. I added `SENTRY_DSN` (+ `SENTRY_ENVIRONMENT: production`) to [render.yaml](../render.yaml) as `sync: false` so the blueprint documents it; you still enter the value in the Render dashboard.
>
> **You confirm (remote, not visible to me):** that the GitHub Actions secrets and the Render `SENTRY_DSN` value are actually populated. Final proof is the forced-500 test in Section 4.

**Why this matters:** The Sentry SDK is wired into both backend and frontend, but it's a **no-op until the DSN env vars are set**. Until then you're flying blind on staging/prod errors.

### 2.1 — Backend (Render) 👤
- Render dashboard → backend service → **Environment** → add `SENTRY_DSN` = your backend project DSN → save (redeploys).

### 2.2 — Frontend (build-time, GitHub Actions secrets) 👤
The frontend DSN is baked in at build time, and source maps upload during the deploy job. Add these as **GitHub → repo Settings → Secrets and variables → Actions**:
- `VITE_SENTRY_DSN` — frontend project DSN
- `SENTRY_AUTH_TOKEN` — for source-map upload
- `SENTRY_ORG` — your Sentry org slug
- `SENTRY_PROJECT` — your Sentry frontend project slug

> If the three source-map secrets are absent, the upload step just warns and is skipped — but you lose readable stack traces, so set them.

**✅ Done when:** an intentional test error in staging shows up in Sentry with a `request_id` and scrubbed payload (you'll confirm this in Section 4).

---

## Section 3 — 🟠 Turn on branch protection for `main` — ✅ DONE (2026-06-04)

**Why this matters:** CI exists but nothing forces it. Right now someone can push straight to `main` and bypass tests.

### 3.1 — Configure (needs repo-admin) 👤
- GitHub → repo **Settings** → **Branches** → **Add branch ruleset** (or classic "Branch protection rule") for `main`:
  - ✅ Require a pull request before merging
  - ✅ Require status checks to pass before merging → select the **CI** checks (pytest, ruff, eslint, tsc, vitest, Alembic single-head)
  - ✅ Require branches to be up to date before merging
  - ✅ Block direct pushes (do not allow bypassing the above)

**✅ Done when:** a direct push to `main` is rejected and a PR cannot merge with red CI.

---

## Section 4 — 🟡 Staging verification (Month 1 sign-off) — 🟡 code-level verified; staging walk-through still required (2026-06-04)

> **Done this session (code level):** `tests/test_data_lifecycle.py` **passes** against a clean migrated Postgres (org delete purges all tenant rows + writes audit log; export streams JSON + audits). This is the local equivalent of task 4.1.
> **Still yours to do:** 4.1 against the **staging** DB (real data shapes) and the **manual staging walk-through** (4.2) — these need the live environment, a login, and the forced-500 → Sentry check, none of which I can reach.

**Why this matters:** CI proves schema correctness against a fresh local Postgres. It does **not** prove the cascade/delete/export behaves against real-shaped staging data, nor that the labeled dashboard and Sentry pipeline work end to end.

### 4.1 — Run the data-lifecycle test against staging 🧑‍💻
- Point the test config at the **staging** database (not local CI Postgres) and run:
  ```
  cd backend && pytest tests/test_data_lifecycle.py
  ```
- Confirms org delete purges all tenant tables and export streams correctly against real data shapes.
- ⚠️ Use a throwaway/staging org — this deletes data.

### 4.2 — Manual staging walk-through 🧑‍💻
Do this in the staging environment, in order, and tick each:
- [ ] Log in successfully.
- [ ] Dashboard renders with **source/freshness labels** (SourceBadge + DataFreshness) on widgets.
- [ ] Mark an org `is_demo` → the **DemoBanner** appears (and does not flash on load).
- [ ] Delete a throwaway org via the API → its assets/scan_runs/findings are gone.
- [ ] Export that org's data as JSON before deleting (or on another test org).
- [ ] Trigger an intentional 500 → confirm a **Sentry event** arrives with a `request_id` and a **scrubbed** payload (no email/token/hostname leaking).

**✅ Done when:** every box above is ticked in staging.

---

## Section 5 — 🟡 Month 2 runtime verification (Definition-of-Done boxes) — 🟡 code-level verified; live checks still required (2026-06-04)

> **Done this session (code level):** the Month 2 suites all **pass** against a clean migrated DB — `test_inventory_import_service`, `test_inventory_routes`, `test_inventory_findings_and_health`, `test_assets`, `test_scan_runs`, `test_epss_ingest`, `test_analytics_events` (incl. PII-scrub), `test_assessment_intake_*`, `test_m365_integration`. Full backend suite: **537 passed, 1 skipped**. The full Alembic chain `032→044` also applies cleanly.
> **Still yours to do (live, I can't reach these):** a real fresh-signup CSV→KEV walk-through, confirming the scheduled EPSS job populates the DB after 02:00 UTC, and the M365 OAuth flow against a real test tenant (needs the Azure AD app registered).

**Why this matters:** The Month 2 code is verified to *exist and pass tests*, but the plan's Definition-of-Done still needs these behaviors confirmed by an actual run against live data/services.

- [ ] **CSV → assets → KEV match for a fresh org:** sign up → create org with name + domain only → download the sample CSV (`frontend/public/sample-inventory.csv`) → upload it → see assets populate and at least one "preliminary" KEV match within ~2 min.
- [ ] **EPSS scheduled run:** after the scheduled EPSS job runs (daily 02:00 UTC), confirm `epss_percentile` / `epss_fetched_at` are populated on `cves` and the "Exploitability" column shows in the NVD table.
- [ ] **M365 OAuth spike (staging):** with `ENABLE_M365_INTEGRATION` on, connect a **test M365 tenant** → complete consent → run "Sync now" → devices appear as `assets`.
  - ⚠️ Prereq: an Azure AD app must be registered (app ID/tenant documented in [m365_integration_notes.md](m365_integration_notes.md)) and the redirect URI must match staging exactly.
- [ ] **Activation analytics, no PII:** trigger a few events (skip an intake step, start/complete a CSV upload) and confirm `activation_events` rows contain **no** hostnames/IPs/emails.

> Reference scripts: [manual_test_month2.md](manual_test_month2.md) (local) and [live_test_month2.md](live_test_month2.md) (production walk-through).

**✅ Done when:** all four behaviors are confirmed on staging.

---

## Section 6 — 🟢 Prevent the leak from recurring (hardening)

**Why this matters:** Defense-in-depth so a future commit can't reintroduce a leaked secret. (This is a small CI/config addition, not feature code.)

### 6.1 — Add a secret scanner 🧑‍💻
Pick one:
- **Pre-commit hook:** add `gitleaks` or `detect-secrets` to `.pre-commit-config.yaml`.
- **CI step:** add a `gitleaks`/`detect-secrets` job to `.github/workflows/ci.yml` so the leak class fails the build.

### 6.2 — Record the closure 🧑‍💻
- Once Section 1 is done, add a one-line note (rotation date) to [month_1_execution_plan.md](month_1_execution_plan.md) and close out its "Pre-existing finding" section.

**✅ Done when:** a secret-shaped string in a doc/commit is caught automatically, and the rotation date is recorded.

---

## Master checklist

**Critical / blocker**
- [x] New NVD key issued + live (Render + all local `.env`)
- [ ] Old NVD key revoked by NIST (email confirmation) — *confirm if not already done*
- [x] New Census key issued + live; old one documented as compromised

**High**
- [x] `SENTRY_DSN` set in Render *(value entered by you; render.yaml now declares it)*
- [x] `VITE_SENTRY_DSN` + `SENTRY_AUTH_TOKEN` + `SENTRY_ORG` + `SENTRY_PROJECT` set in GitHub Actions secrets
- [x] Branch protection enabled on `main` with required CI checks

**Verification**
- [x] `test_data_lifecycle.py` passes (clean local DB) — [ ] still run against **staging** DB
- [ ] Month 1 manual staging walk-through complete (all 6 boxes)
- [x] Month 2 backend suites pass (clean local DB) — [ ] still confirm **live** CSV→KEV, EPSS run, M365 OAuth

**Hardening**
- [ ] Secret scanner added (pre-commit or CI)
- [ ] Rotation date recorded in `month_1_execution_plan.md`; "Pre-existing finding" closed

---

## Notes / dependencies
- **Azure AD app registration** is a prerequisite for the M365 staging test (Section 5) — if not done, that one check is blocked until someone registers the app.
- Everything in Section 1 requires **provider portal access** (NIST/Census) and **Render access** — route to whoever holds those.
- None of these block ongoing Month 3 code work, **except** key rotation blocks starting real **pilots**.
