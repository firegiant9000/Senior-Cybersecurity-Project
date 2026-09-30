# Hacker Tracker roadmap review, September 2026

_Prepared 2026-09-29 against `origin/main` at `5ab0b38`. Read-only audit of the repository, its planning documents and CI. Nothing here is a measured result. Line references are to that commit._

This review is the evidence base for the 2026-09 revision recorded in [`PRODUCT_VIABILITY_ROADMAP.md`](PRODUCT_VIABILITY_ROADMAP.md) (the public commitment record, now the canonical roadmap) and the revision note at the top of [`hacker_tracker_6_month_development_plan.md`](hacker_tracker_6_month_development_plan.md).

## 1. Reframing decision

Hacker Tracker was planned as a possible SMB/MSP security product ("lightweight SMB vulnerability/exposure management platform"). As of this review it is reframed as **an AppSec and DevSecOps reference implementation that also functions as an exposure-management prototype**. The product capabilities stay; what changes is what gets built next. The next work is assurance of the security product itself (a threat model, an authorization suite, scanning gates, a signed and attested release, matcher accuracy measured against an independent reference), not more breadth.

The reason: a security product with no threat model, no dependency audit, globally mocked authentication in tests, tenancy by handler convention, no security headers and zero releases has a credibility gap that is cheap to close and that produces exactly the evidence AppSec and DevSecOps roles ask for. Market breadth does not.

## 2. Current roadmap goals (as written before this revision)

Two documents disagree. `PRODUCT_VIABILITY_ROADMAP.md` still says "Where we are today (Month 2 — May 2026)" and lists Months 3 to 6 as vendor aliasing and PDF export, retention and scheduling, real IC3 ingestion, and SOC 2 scoping. The 6-month plan (`hacker_tracker_6_month_development_plan.md`, 2,091 lines) has Months 1 to 4 done or partly done and Months 5 and 6 as asset dashboard, PDF and email reports, forecasting, Windows scanner, multi-tenancy isolation tests, an MSP console, a security questionnaire pack, hardening (secret scanning, dependency scanning, "basic threat model document"), a backup restore drill and an optional macOS scanner.

| Plan item | Stated status | Verified |
|---|---|---|
| Week 0 validation gate (5 to 8 interviews, go/no-go memo) | "pending ... deferred under accepted risk" | Two interviews exist (`docs/validation_interviews.md`), both self-discounted |
| Month 1 stabilise, instrument, harden CI | "Code-complete on PR #164" | CI, JSON logging, Sentry scrubber present |
| Month 2 onboarding and inventory upload | delivered | CSV upload and KEV literal match present; CycloneDX SBOM import (#115) deferred |
| Month 3 EPSS, CPE matcher, risk scoring | matcher gate passes | 51-case fixture, 95 % floor, 0 high-confidence FP; nightly run succeeded 2026-09-29 |
| Month 4 Linux read-only scanner and agent trust model | Linux scanner and token flow in code | Verified (section 3) |
| Month 5 dashboard, PDF reports, forecasting, Windows scanner, tenancy tests | unmarked | Windows scanner and tenancy tests not found |
| Month 6 MSP console, questionnaire pack, hardening, restore drill | unmarked | None found |

## 3. Already implemented (verified in code)

- **Agent** (`agent/`): Go 1.22, stdlib only (`go.mod:7-9`), read-only, no inbound listener, 64 KB response `LimitReader` (`upload/client.go:80,119`).
- **Agent tokens**: `ht_<prefix>_<secret>` with a 256-bit `token_urlsafe` secret, sha256 at rest, `hmac.compare_digest` verification, 365-day default expiry, rotation with a 24-hour grace, revoke (`backend/app/services/agent_token.py:8-204`; `config.py:165-167`).
- **Replay guard**: unique `(scan_id, nonce)` (`db/agent_scan_nonce.py:23`), 24-hour fast path, marker written in the same transaction as the import, `IntegrityError` mapped to 409 (`routes/v1/inventory.py:469-531`).
- **Upload caps**: 50,000 items per list, string length limits, `extra="forbid"` (`schemas/agent_scan.py:84-86`); 12 requests per minute per token prefix.
- **Matcher calibration gate**: `tests/regression/matcher_known_good.py` with `MIN_PASS_RATE = 0.95`, `MAX_HIGH_CONF_FP_RATE = 0.02`, a hard zero on high-confidence false positives, nightly workflow.
- **Logging**: JSON with `request_id`, `org_id`, `user_id` contextvars; inbound `X-Request-ID` honoured and echoed (`core/logging.py`, `core/observability.py:127-153`).
- **Sentry PII scrubber** with a test that keeps backend and frontend key lists aligned (`test_observability_scrubber.py`).
- **CI**: ruff, pytest on PostgreSQL 15, single-Alembic-head check (blocking), ESLint with zero warnings, `tsc`, Vitest, `go vet` and `go test`, gitleaks on push, PR and weekly, post-deploy health check. Dependabot monthly, grouped.
- **Tests**: 644 `def test_` in the backend, 466 Vitest cases, 9 Go tests.
- **Non-root backend container** (`backend/Dockerfile:19-22`).

## 4. Claimed but unproven or contradicted

| Claim | Where | What the code shows |
|---|---|---|
| "Signed agent releases" | `README.md:119-123` | `agent-release.yml` has never run; there are no tags and no releases; signing is a GPG step conditional on a secret whose existence is unknown; without it the workflow publishes an unsigned prerelease. The workflow's doc link points to a path that does not exist (`docs/agent_release_signing.md`; the file is under `docs/security/`). |
| "AI prompts receive data as JSON, not interpolated prose" | `README.md:153` | Findings are JSON, but org name, industry, employee range and state are f-string-interpolated into the prompt with no delimiters (`services/ai_summary.py:104-109,151`). No injection test exists. |
| "Every organization-scoped route takes the org ID and checks membership server-side" | `README.md:138-139` | Most routes derive the org from `users.org_id` via `get_current_org`; global admins bypass every org check by design (`core/dependencies.py:107-126,164-173`). There is no route-enumerating test. |
| CI runs `alembic check` | `README.md:262-263` | It runs with `continue-on-error` (`ci.yml:93-95`). |
| "50 migrations" | `README.md:83` | 49 files; revision number 021 is used twice; 024 and 041 are missing. |
| Roles are admin/member | `README.md:135-137` | Global roles are viewer/member/admin and org roles member/admin/owner (`dependencies.py:129-133`). |
| "We do not install agents" | `PRODUCT_VIABILITY_ROADMAP.md:99` | A Go host agent shipped in Month 4. |
| Multi-tenancy isolation tests, `threat_model_tenancy.md`, dependency scanning, upload size limit | 6-month plan lines 241, 1353-1355, 1458-1471, 1724, 1902 | None exist. `backend/tests/security/` does not exist. No body-size limit on `POST /inventory/scans`. |
| Auth tests exercise Firebase verification | implied by the README's security section | `tests/conftest.py:29-47` autouse-patches `verify_id_token` for every test; any bearer string is accepted. |

## 5. Defects and gaps confirmed by inspection

1. **Email-rebind account takeover path.** `routes/v1/auth.py:62-70` matches an unknown `firebase_uid` to an existing local user by email and rebinds it, without checking `email_verified`. An unverified Firebase account claiming a victim's address takes over that local user. `check_revoked` is also not used. **Fixed 2026-09-30 in PR #192** (verified email and an unbound row are both required; revocation is checked).
2. **No security headers** on the API (`main.py:184-207` has only request-context, SlowAPI and CORS middleware) or on Firebase Hosting (`firebase.json` has no `headers` block).
3. **Rate limiting is in-memory per process** (`core/limiter.py:7`), keyed by `get_remote_address`, which behind Render's proxy may be the proxy address.
4. **`/health` is static** (`routes/health.py:20-28`); the post-deploy check tests only for HTTP 200.
5. **Stale backend pins**: fastapi 0.104.1, sqlalchemy 2.0.23, pydantic 2.5.3, python-multipart 0.0.6 (`backend/requirements.txt`); no lockfile or hashes; pytest and ruff in the production requirements; Go 1.22 is past upstream support; Dependabot ignores major bumps and its latest pip run failed.
6. **Global auth mock in tests** (`tests/conftest.py:29-47`).
7. **Tenancy by convention**: 71 usages of four dependency helpers across 9 routers, no middleware, no classification table, roughly 120 routes across 24 router files.
8. **Prompt injection surface** in `ai_summary.py` (see section 4).
9. **CI actions unpinned** (all floating tags), no top-level `permissions:` in `ci.yml`, a deploy-hook secret interpolated directly into a `run:` script (`ci.yml:316`).
10. **Duplicate Alembic revision number 021**; drift check advisory only.
11. **Matcher accuracy is a regression number, not a real-world number**: no distro backport handling, no comparison against Trivy or Grype.
12. **Frontend prod Dockerfile** runs `npm ci --only=production` then `npm run preview` (Vite is a devDependency) and runs as root; not used for production, but misleading.

## 6. Technically useful future work (kept or added)

The six milestones S1 to S6 in `PRODUCT_VIABILITY_ROADMAP.md`: real attested agent release with SBOM; dependency and supply-chain gates; STRIDE threat model; route-enumerating authorization suite with real token verification; DAST and manual AppSec; matcher validation against Trivy or Grype on real images. Plus the optional dogfooding extension: ingest CycloneDX SBOMs from the author's own repositories and show dependency inventory, KEV status and EPSS priority.

Old plan items that survive:
- 6.3 "Add secret scanning in CI" is done (gitleaks). "Add dependency scanning" and "basic threat model document" are promoted to S2 and S3 with real acceptance criteria.
- 5.4 "Multi-tenancy isolation tests" is promoted to S4.
- 6.4 backup restore drill: kept as OPTIONAL. Render's free-tier Postgres has no backups; a `pg_dump` and restore drill with row counts is worth one afternoon and one paragraph in the README, but it is not on the critical path.
- CycloneDX SBOM import (#115, deferred in Month 2): becomes the optional personal-use extension, since the same code path is now needed to consume the S1 SBOM.

## 7. Feature work that should stop

| Item | Old plan | Decision | Reason |
|---|---|---|---|
| MSP / client management console (6.2) | Month 6 | CANCELLED | Sales-heavy platform work; incumbents priced for it; no evidence value. |
| Windows scanner (5.3), macOS scanner (6.5) | Months 5 and 6 | CANCELLED | Agent OS breadth proves nothing new about security engineering; Linux agent is enough to carry the release, SBOM and provenance story. |
| Executive and technical PDF reports, email-delivered reports (5.2, 5.2.2) | Month 5 | CANCELLED | Reporting breadth. |
| Forecasting MVP (5.2.5) | Month 5 | CANCELLED | Speculative analytics. |
| Asset dashboard expansion (5.1) | Month 5 | DEFERRED | UI breadth; revisit only if the dogfooding extension needs a specific view. |
| Security questionnaire pack (6.0), SOC 2 Type I scoping, status page | Month 6, viability roadmap Month 6 | CANCELLED | Compliance theatre for a project with no customers. The STRIDE threat model is the honest substitute. |
| Real IC3 ingestion, multi-year backfill (viability roadmap Month 5), open PR #170 ingest cron scheduling | Month 5 | DEFERRED | Economic and IC3 correlation is the teammate's contribution (Ethan Gagliano) and dilutes the security-engineering story. PR #170 is small and may merge on its own merits, but no further work here. |
| M365 / Entra device discovery expansion | Month 2 spike | DEFERRED | Stays behind its flag; no expansion. |
| Vendor alerts, anomaly detection breadth, more AI features | various | DEFERRED | Only the injection hardening of the existing AI summary is in scope (S5). |
| Week 0 validation interviews, "first paid pilots", pilot readiness (6.1) | Week 0, Month 3, Month 6 | CANCELLED | Not a commercial project. |
| Agent auto-update (design doc only) | Month 4 Phase 6 | DEFERRED | Revisit only after S1 has produced two attested releases and an upgrade path is worth proving. |

## 8. Roadmap contradictions

- The viability roadmap says "we do not install agents"; the product ships an agent. Corrected in the revision.
- The viability roadmap is dated Month 2 (May 2026); the 6-month plan and the README say Month 4. The revision restates "where we are".
- The 6-month plan's Month 5 and 6 promise assurance work (tenancy tests, threat model, dependency scanning) as a late-stage add-on. The revision makes that work the whole roadmap.
- `docs/IMPLEMENTATION_PLAN.md:24,28` still tell the reader to uncomment CI steps that are already active.
- `docs/IMPLEMENTATION_PLAN.md:34` lists "Enforce email verification" as an optional future enhancement; section 5 shows it is a takeover path.

## 9. Current risks

- ~~The email-rebind path (section 5, item 1) is exploitable today against the deployed pilot.~~ Fixed 2026-09-30 in PR #192 and deployed. Its remaining follow-up (auto-created accounts store unverified emails) is an S3 input.
- Stale pins with published advisories in a public security tool.
- The pilot deployment on Render uses free-tier Postgres with no backups.
- Public repository with a Firebase project ID and Render blueprint in the tree; no secrets found, but the gitleaks allowlist should be reviewed when actions are pinned.
- PR #170's body carries a "Generated with Claude Code" line, against the author's stated preference; edit the body before merging.

## 10. Evidence gaps (what does not exist yet, in the order the revision closes them)

1. A release. Any release.
2. An SBOM and verifiable provenance for that release.
3. Blocking SAST, SCA and container-scan gates with recorded thresholds.
4. A threat model that maps threats to controls, tests, accepted risks or open risks.
5. A test that enumerates every route and fails on an unclassified one.
6. A cross-tenant test that uses real token verification.
7. A DAST baseline result.
8. A precision and recall number for the matcher against an independent reference on real images.

## 11. Repository housekeeping observed (no action taken)

- Local clone `main` on the author's machine diverged from `origin/main` (561 ahead, 568 behind) because of the pre-publication history rewrite; use `origin/main` or a fresh worktree.
- Three stale feature branches remain on the remote after the rewrite (`feature/adding-ic3-2025`, `feature/assessment-submission`, `feature/month2-onboarding-inventory`).
- Duplicate Alembic revision 021 should be resolved with a no-op merge revision, not by renumbering history.
