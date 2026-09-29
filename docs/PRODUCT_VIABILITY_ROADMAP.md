# Product Viability Roadmap

This document is the public commitment record for what Hacker Tracker can and
cannot do today, and what we are working toward. It is intentionally honest:
prospects, design partners, and reviewers should be able to read this and know
exactly where we are.

Companion docs:
- [DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md) — per-widget data backing
- [pii_inventory.md](security/pii_inventory.md) — what personal data we collect/log
- [privacy.md](security/privacy.md) — user-facing privacy promise

---

## Revision 2026-09-29: AppSec / DevSecOps reference implementation

_This revision supersedes the "Roadmap" and "Non-goals" sections below, which are kept as history with status tags. It also supersedes Months 5 and 6 of [`hacker_tracker_6_month_development_plan.md`](hacker_tracker_6_month_development_plan.md). Evidence for every decision is in [`roadmap-review-2026-09.md`](roadmap-review-2026-09.md), verified against `origin/main` at `5ab0b38`._

### R1. Decision

Hacker Tracker is no longer planned as a possible SMB or MSP security startup. It is **an application-security and DevSecOps reference implementation that also works as an exposure-management prototype**. The working product (NVD, KEV and EPSS correlation, CSV and agent inventory, CPE matcher with a calibration gate, risk scoring, executive summary) stays as it is. What gets built next is assurance of that product: a threat model, an authorization suite, blocking scanning gates, a signed and attested agent release with an SBOM, a DAST baseline, and a measured matcher accuracy against an independent reference. No new market-facing breadth.

This repository owns, for the whole portfolio: threat modelling, SAST/SCA/DAST gates, authorization assurance, SBOM and build provenance. It does not take on infrastructure as code, OpenTelemetry or load testing; those belong to FairTix.

### R2. Where we are today (2026-09-29)

Month 4 of the six-month plan is code-complete: Linux read-only Go agent, hash-only rotating agent tokens with replay protection, CSV and agent inventory, CPE matcher with a nightly calibration gate (51 self-authored cases, 95 % floor, zero high-confidence false positives), EPSS, JSON logging with correlation IDs, a Sentry PII scrubber with a sync test, PostgreSQL-backed CI with a single-head migration check, gitleaks, Dependabot. Pilot deployed on Render and Firebase Hosting; idle since June.

What does not exist: any release (the release workflow has never run), any SBOM or provenance, any SAST or dependency audit, a threat model (promised at four places in the plan), a cross-tenant test suite (promised as `backend/tests/security/test_tenancy_isolation.py`), security headers, real token verification in tests (a global autouse mock accepts any bearer string), and any real-world matcher accuracy number. One concrete defect: the email-link sign-in fallback rebinds an existing local user by email without checking `email_verified` (`backend/app/api/routes/v1/auth.py:62-70`), which is an account-takeover path. That is fixed first, before S1.

### R3. Status of the previous roadmap items

| Item | Status | Previous goal | New decision and reason | Effect on usefulness | Effect on evidence |
|---|---|---|---|---|---|
| Month 1 stabilise and foundations | CURRENT (done) | CI, Sentry, logging, lifecycle endpoints | Done. | n/a | Baseline |
| Month 2 onboarding wedge and inventory | CURRENT (done) | CSV inventory, EPSS, activation analytics | Done. CycloneDX SBOM import (#115) moves to the OPTIONAL dogfooding extension. | n/a | Baseline |
| Month 3 vendor aliasing, PDF export, first paid pilots | SUPERSEDED | Commercial pilots | Vendor aliasing shipped; PDF export and paid pilots CANCELLED (not a commercial project). | Low | None |
| Month 4 retention, cron domain checks, KEV diff alerts | CURRENT (done) / DEFERRED | Retention and scheduling | Retention shipped. KEV diff alerts and PR #170 ingest cron: DEFERRED, no assurance value. | Low | None |
| Month 5 real IC3 ingestion and backfill | DEFERRED | Replace the static IC3 snapshot | Economic and IC3 correlation is the teammate's contribution and dilutes the security-engineering story. Stays as-is, labelled static. | Low | None |
| Month 6 SOC 2 Type I scoping, export contract, status page | CANCELLED | Production readiness | Compliance theatre with no customers. The STRIDE threat model (S3) is the honest substitute. | None | Replaced by S3 |
| 6-month plan 5.1 asset dashboard expansion | DEFERRED | UI | Revisit only if the dogfooding extension needs a view. | Medium | None |
| 5.2 PDF and email reports, 5.2.5 forecasting | CANCELLED | Reporting breadth | No evidence. | Low | None |
| 5.3 Windows scanner, 6.5 macOS scanner | CANCELLED | OS coverage | Agent breadth proves nothing new; the Linux agent carries the release and provenance story. | Medium for a product, none here | None |
| 5.4 multi-tenancy isolation tests | SUPERSEDED | Tests before the MSP path | Promoted to S4 with a route-enumeration requirement and real token verification. | None | Core AppSec evidence |
| 6.0 security questionnaire pack | CANCELLED | Partner questionnaire | Replaced by S3. | None | Replaced |
| 6.1 validation and pilot readiness, Week 0 interviews | CANCELLED | Customer validation | Not a commercial project. | n/a | n/a |
| 6.2 MSP / client management console | CANCELLED | Multi-client console | Platform breadth for a saturated market. | None | None |
| 6.3 hardening: secret scanning | CURRENT (done) | gitleaks | Done. | n/a | Baseline |
| 6.3 hardening: dependency scanning, upload limits, basic threat model | SUPERSEDED | Late-stage add-ons | Promoted to S2, S3 and S4 with acceptance criteria. | None | The roadmap |
| 6.4 backup restore drill | OPTIONAL | Restore drill on the pilot DB | Worth one afternoon (`pg_dump`, restore, row counts, README paragraph); not on the critical path. | Low | Small |
| Agent auto-update design | DEFERRED | Auto-update | Revisit after two attested releases exist. | Medium | None yet |
| Non-goal "we do not install agents" | SUPERSEDED | No agents | An agent shipped in Month 4; the non-goal is rewritten below. | n/a | n/a |
| Non-goals: no active scanning without consent, no exploit code, no managed SOC | CURRENT | Boundaries | Unchanged. | n/a | n/a |

### R4. Milestones

Each milestone lists its acceptance criterion, the artifact it produces, a resume bullet with placeholders that are not filled until the work is done, and the interview questions it prepares for. S0 is a prerequisite fix, not a milestone.

#### S0. Fix the email-rebind takeover path

Require `email_verified` before matching an unknown Firebase UID to an existing local user by email; use `check_revoked=True` on verification. Add the test that reproduces the takeover before the fix and passes after. Ship to the pilot.

#### S1. A real agent release: `agent-v0.1.0` with SBOM and provenance

Work: tag `agent-v0.1.0` and let the existing workflow run once, as-is, to learn what breaks. Then replace the secret-dependent GPG step with **GitHub artifact attestations** (`actions/attest-build-provenance`, keyless, Sigstore-backed, no stored key) and optionally cosign keyless signing of the binaries; generate a **CycloneDX SBOM** for the agent (`cyclonedx-gomod` or syft) and attach it to the release, attested as well (`actions/attest-sbom`). Add a `verify` job that downloads the release asset and runs `gh attestation verify` against it. Fix the workflow's broken documentation path. Write `docs/security/agent_release_verification.md` with the exact commands a consumer runs.

**Acceptance.** A GitHub Release `agent-v0.1.0` exists with linux/amd64 and arm64 binaries, `SHA256SUMS`, a CycloneDX SBOM, and provenance attestations; `gh attestation verify` passes in a CI job and in the documented manual steps; no signing secret exists in the repository settings.

**Evidence produced.** The release page, the attestation, the SBOM file, the verify job log.

**Resume potential.** "Shipped the Hacker Tracker host agent with keyless build provenance (GitHub artifact attestations, Sigstore) and a CycloneDX SBOM, verifiable with `gh attestation verify`; replaced a secret-dependent GPG signing step."

**Interview questions.**
- What does a build provenance attestation prove, and what does it not prove?
- Why keyless signing instead of a stored GPG key? What is the trust root?
- What is in the SBOM, and how would a consumer use it after a new CVE drops?
- How would you detect that someone tampered with the release asset after publication?

#### S2. Dependency and supply-chain hardening

Work: blocking CI gates for each language: **CodeQL** (Python, JavaScript/TypeScript, Go) on PR and weekly; **pip-audit** with a lockfile or hashes for the backend (introduce `requirements.lock` or `uv.lock`); **govulncheck** for the agent; **npm audit** at high severity for the frontend; **Trivy** on the backend image with CRITICAL and HIGH failing; **Semgrep** with a small curated ruleset if it catches something CodeQL does not (drop it if not). Pin every GitHub Action to a commit SHA; add a top-level `permissions: contents: read` to every workflow; move the Render deploy-hook secret out of shell interpolation. Upgrade the 2023-vintage backend pins (fastapi, starlette, pydantic, python-multipart, sqlalchemy) and Go to a supported version; fix what breaks. Remove pytest and ruff from the production requirements. Document allowed exceptions in `docs/security/scan_exceptions.md` with an expiry date for each.

**Acceptance.** Five gates (CodeQL, pip-audit, govulncheck, npm audit, Trivy) are required on `main`; all green; every action pinned by SHA; every exception documented with an expiry; the pip Dependabot job passes.

**Evidence produced.** The workflow files, one green run of each gate, the exceptions document.

**Resume potential.** "Added blocking SAST, dependency-audit and container-scan gates (CodeQL, pip-audit, govulncheck, npm audit, Trivy) to a FastAPI, React and Go codebase, pinned every CI action to a commit SHA, and upgraded [N] out-of-date dependencies with published advisories."

**Interview questions.**
- Why pin Actions to SHAs rather than tags? What attack does it stop?
- When is a scanner exception acceptable, and how do you stop it becoming permanent?
- What is the difference between what CodeQL finds and what pip-audit finds?
- Why should test tooling not be in the production image?

#### S3. STRIDE threat model

Work: `docs/security/threat_model.md` covering agent enrollment, agent upload, token lifecycle and rotation, replay, human authentication (including the email-link fallback), organization tenancy, the global-admin boundary, the ingestion pipeline (NVD, KEV, EPSS) and the AI summary inputs. For every threat, one of: **CONTROL** (with the file and line), **TEST** (with the test name), **ACCEPTED RISK** (with the reason and owner), or **OPEN RISK** (with the milestone that closes it). The threat model drives S4 and S5: every OPEN RISK must map to a later item or be explicitly accepted.

**Acceptance.** Every threat row has exactly one classification; every TEST row names a test that exists; every OPEN RISK names a milestone; the document is linked from the README security section.

**Evidence produced.** The threat model document.

**Resume potential.** "Wrote a STRIDE threat model for Hacker Tracker's agent enrollment, upload, token lifecycle, tenancy and AI-input paths ([N] threats), mapping each to a control, a test or an accepted risk, and used it to drive the authorization suite."

**Interview questions.**
- Walk me through the spoofing and tampering threats on the agent upload path and how each is controlled.
- Why is client-chosen `(scan_id, nonce)` weaker than a timestamped, signed request, and did you accept that?
- What is the global-admin boundary and why is cross-tenant access "by design" there?
- What threat did writing the model surface that you had not considered?

#### S4. Authorization assurance

Work: a **route-enumerating authorization suite**. A test walks the FastAPI router, requires every route to appear in a classification table (`public`, `authenticated-global`, `organization-scoped`, `agent`, `administrator`), and fails CI on any unclassified route. For organization-scoped routes it issues requests as a member of org B against org A's resources and expects 403 or 404 (never 200, never 500). It also tests member vs admin on admin-only routes, a revoked agent token, an expired rotated token past its grace, a replayed upload, and the public endpoint boundary. These tests use **real token verification**: Firebase emulator or a locally signed test key with the real verification code path, not the autouse mock. Add security headers middleware (and a `headers` block in `firebase.json`), a body-size limit on the agent upload route, and a `/health` that checks the database.

**Acceptance.** Unclassified routes: 0. Cross-tenant leaks: 0. Routes returning 500 on a denied request: 0. The suite runs with the autouse auth mock disabled. The classification table is committed and counted.

**Evidence produced.** The suite, the classification table, a CI run showing the route count.

**Resume potential.** "Built a route-enumerating authorization suite over [N] API endpoints that fails CI on any unclassified route and verifies cross-tenant isolation with real token verification; found and fixed [K] mis-scoped or unclassified routes and added security headers and an upload body limit."

**Interview questions.**
- How does the suite guarantee a new route cannot ship unclassified?
- Why does a cross-tenant test with a mocked verifier prove less than one with real verification?
- 403 or 404 for a cross-tenant read? Why?
- How do you test token rotation grace without sleeping?

#### S5. DAST and manual AppSec

Work: **OWASP ZAP baseline** against the docker-compose stack in CI, failing at medium and above once the header work in S4 lands. Harden the AI summary prompt: delimit and escape org-supplied fields, add a prompt-injection test corpus, validate output against the schema. If pursuing BSCP, perform a **manual Burp assessment** of the API and record each finding as: finding, risk, exploit path, fix, regression test.

**Acceptance.** ZAP baseline green at medium and above on every PR; the injection corpus runs in CI; if the Burp assessment is done, `docs/security/assessment-YYYY-MM.md` exists with every finding closed by a regression test or accepted.

**Evidence produced.** ZAP report artifact, injection tests, assessment document.

**Resume potential.** "Integrated an OWASP ZAP baseline scan into CI and performed a manual API assessment with Burp Suite; documented [N] findings with exploit paths and closed each with a fix and a regression test."

**Interview questions.**
- What can a DAST baseline find that SAST cannot, and the reverse?
- Show me one finding from the assessment and its regression test.
- How did you make the AI prompt resistant to instructions embedded in an organisation's own name?

#### S6. Matcher validation against an independent reference

Work: the current 100 % regression number is a self-authored fixture, not real-world accuracy. Run the agent on at least three real images (Debian stable, Ubuntu LTS, a RHEL-family image) and compare findings against **Trivy** or **Grype** on the same images as the reference. Measure precision, recall and F1 per confidence tier, high-confidence false positives, false negatives, and specifically the distro-backport mismatch rate (a package whose distro version is patched but whose upstream version string matches a CVE). Document methodology and limitations in `docs/matcher_evaluation.md`. Decide from the numbers whether backport awareness (distro security trackers) is worth building; do not build it before measuring.

**Acceptance.** Numbers for three images committed with the reference tool version, the agent version, the image digests and the comparison script; the README's matcher claim rewritten to quote them; the backport gap either scoped as a follow-up or explicitly accepted.

**Evidence produced.** Evaluation document, comparison script, raw outputs.

**Resume potential.** "Measured the Hacker Tracker CPE matcher at [P] % precision and [R] % recall against Trivy on [N] real Linux images and documented the distro-backport gap as the dominant false-positive cause."

**Interview questions.**
- Why is a regression gate not an accuracy measurement?
- What is a distro backport and why does naive version matching get it wrong?
- How did you choose the reference tool, and what are its own error modes?
- What would you build first to raise recall, and what would you build first to raise precision?

#### Optional: dogfooding on my own SBOMs

Ingest CycloneDX SBOMs produced by the author's other repositories (FairTix, PlanPal, TomeStack CI can emit them) through the deferred #115 import path, and show dependency inventory, KEV status and EPSS priority per repository. This is personal tooling and a test of the matcher on a second input type. It does not compete with OWASP Dependency-Track and the README must say so.

**Acceptance.** One SBOM from another repository imported and matched; a screenshot in the README; the Dependency-Track disclaimer present.

### R5. Do not do (2026-09 revision)

MSP management console, Windows or macOS agent, generic attack-surface platform, additional threat-intelligence feeds, M365 expansion, more economic-data correlation, arbitrary AI features, PDF or email reports, forecasting, SOC 2 scoping, customer interviews, Terraform, OpenTelemetry, load testing (except one optional test of the synchronous agent upload at the 50,000-item cap).

### R6. Non-goals (restated 2026-09-29)

- The agent is read-only, stdlib-only, shell-out-only and opens no listener. It never executes remediation.
- No active scanning of customer infrastructure without explicit consent.
- No storage of exploit code or weaponised payloads.
- Not a managed-SOC service and not a commercial product.

---

## Where we are today (Month 2 — May 2026) — SUPERSEDED 2026-09-29 (see R2)

**Position:** early-stage MSP/SMB-facing cyber threat intelligence platform.
Out of academic prototype, not yet generally available.

**Real, working capabilities:**
- Live NVD CVE ingestion with severity / KEV labelling.
- EPSS (Exploit Prediction Scoring System) probabilities and percentile rank
  on every CVE the NVD ingest sees, refreshed daily.
- Per-org vendor matching against CISA KEV.
- Org onboarding "fast path": new user can reach a populated dashboard with
  just org name + primary domain — assessment intake is non-blocking.
- CSV asset inventory upload (drag-drop, preview, idempotent import) with
  a preliminary literal-match KEV cross-reference per asset.
- Per-asset CVE drill-down (KEV-listed CVEs first; full vendor/version
  matching arrives in Month 3 with the CPE matcher).
- Inventory health card on the dashboard overview.
- Activation analytics for the onboarding funnel (non-PII payloads only).
- Org onboarding, role-based access (Firebase + role gates).
- Static IC3 (FBI Internet Crime Complaint Center) aggregate analytics.
- Composite CVSS + KEV risk scoring per CVE.
- AI-generated executive summaries grounded in the above.

**Honest limits:**
- The asset → CVE matcher is a *literal* vendor+product match for Month 2.
  Expect false positives until the Month 3 CPE matcher lands; the UI
  labels every match as preliminary.
- M365 / Entra device discovery is a working spike (Phase E) but stays
  behind the `ENABLE_M365_INTEGRATION` feature flag — not enabled in prod.
- IC3 incident data is a curated static snapshot of the 2023 annual report,
  not a live feed. Labelled as such everywhere it appears.
- Domain reputation checks (HIBP / Shodan / OTX) are *not* shipped yet — keys
  are wired but the route is gated behind Month 1 Phase E.
- No automated retention / data-lifecycle cron yet (Month 4).
- No SOC 2 or formal compliance certification. Treat us as a research-grade
  decision-support tool, not a system of record.

---

## Roadmap — SUPERSEDED 2026-09-29 (kept as history; statuses in R3)

### Month 1 — Stabilize + Foundations (done)
- CI gating, Sentry observability, structured logging.
- Demo-mode segregation per organization.
- Data lifecycle endpoints (DELETE org, export org).
- Data-source transparency labels on every widget.
- Trust pack (this document).

### Month 2 — Onboarding wedge + inventory MVP (delivered)
- Onboarding collapse: assessment intake is non-blocking; new users reach
  a useful dashboard with org name + primary domain only.
- Asset / inventory data model (`assets`, `asset_software`, `scan_runs`,
  `cpe_match_cache`, `vendor_aliases`) — migrations v034–v037.
- CSV inventory upload, preview, and idempotent import endpoint.
- Per-asset KEV-match findings (literal match; CPE matcher follows in
  Month 3).
- EPSS scheduling + storage; Exploitability column on the NVD table.
- M365 / Entra OAuth spike (behind feature flag, staging only).
- Activation analytics (`activation_events`, migration v039) for the
  onboarding funnel — non-PII payloads only.

### Month 3 — Vendor aliasing + real assessment outcomes (aliasing done; PDF export and paid pilots CANCELLED)
- Canonical `vendor_aliases` table — collapse "MSFT" / "Microsoft" / "ms.com".
- Findings export to PDF.
- First paid pilots.

### Month 4 — Retention + scheduling (retention done; alerts DEFERRED)
- Automated retention enforcement (12 scans/asset default).
- Cron-scheduled domain checks with 24h throttling.
- KEV diff alerts (Slack / email).

### Month 5 — Real IC3 ingestion (DEFERRED)
- Replace static IC3 snapshot with a parser over annual FBI releases.
- Backfill multi-year history.

### Month 6 — Production-readiness (CANCELLED; replaced by S3)
- SOC 2 Type I scoping.
- Customer-managed data export contract.
- Public status page.

---

## Non-goals (deliberately not building) — SUPERSEDED 2026-09-29 by R6

- ~~Endpoint detection / EDR — we do not install agents.~~ (A read-only host agent shipped in Month 4; see R6.)
- Active scanning of customer infrastructure without explicit consent.
- Storing raw exploit code or weaponized payloads.
- A managed-SOC service — we are a tool, not a service.

---

## How to challenge this document

If you read something here that does not match what the product actually does,
file a GitHub issue tagged `trust-pack`. Every claim in this doc should be
falsifiable by inspecting the running system or the codebase.
