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

What does not exist: any release (the release workflow has never run), any SBOM or provenance, any SAST or dependency audit, a threat model (promised at four places in the plan), a cross-tenant test suite (promised as `backend/tests/security/test_tenancy_isolation.py`), security headers, real token verification in tests (a global autouse mock accepts any bearer string), and any real-world matcher accuracy number. One concrete defect found by the review, the email-link sign-in fallback linking an existing local user without checking `email_verified`, was fixed on 2026-09-30 in PR #192 (S0 below).

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

_**Revision 2026-10-18: S5a pulled forward.** A new milestone, **S5a (AI summary quality and injection hardening)**, runs next, ahead of S2. The new order is **S0 (done) → S5a → S2 → S1 → S3 → S4 → S5 → S6**. Reasons:_
- _The AI executive summary has the most visible defects. The code comment in `_build_prompt` (`ai_summary.py:75-76`) and the README claim that org-supplied fields go into a data block, but `org.name`, `industry_label` and `primary_state` are interpolated raw into the prompt (lines 105-108)._
- _The output is not schema-enforced, not grounded in the input findings and not evaluated._
- _The SDK (`google-generativeai==0.8.3`) is deprecated, and the call has no timeout._
- _The fix is Python, the language of most AI-related job postings in a 2026-10-18 sample._

_S2 follows immediately, because the S5a SDK migration and the S2 dependency upgrades touch the same requirements file. **S5a adds no new AI feature, so R5's ban on "arbitrary AI features" stands.** S5a hardens and measures the one feature that already ships. Its prompt-escaping and injection-corpus work was already planned in S5 and moves here from there._

_**Revision 2026-10-19: S5a evaluation made reproducible.** S5a's live evaluation (item 7) now follows [`docs/ai/eval-protocol.md`](ai/eval-protocol.md), with these elements:_
- _pinned model settings;_
- _a versioned dataset with a held-out split that is never used for tuning;_
- _a baseline run before any change;_
- _committed raw responses and failure examples;_
- _cost per summary;_
- _rules for what may be claimed._

_S5a's acceptance and effort below are updated to match, with the earlier text struck through. The milestone order is the one set on 2026-10-18 above, unchanged._

_**Note 2026-10-19: why S2 comes right after S5a.** S5a → S2 → S1: S2 follows S5a because both change `backend/requirements.txt` (S5a pins `google-genai` there; S2 upgrades dependencies and adds the lockfile)._

### R4. Milestones

Each milestone lists its acceptance criterion, the artifact it produces, a resume bullet with placeholders that are not filled until the work is done, and the interview questions it prepares for. S0 is a prerequisite fix, not a milestone.

#### S0. Require a verified email before linking an existing account — DONE 2026-09-30 (PR #192)

The email fallback now links a Firebase account to an existing user only when the token's `email_verified` is true **and** the existing row has no `firebase_uid`; any other email match returns 403 and logs no email or token. `verify_id_token` runs with `check_revoked=True`, so revoked or disabled accounts get 401. Seven tests cover it, and the reproducing test failed before the fix. Deployed to the pilot on merge.

Follow-ups recorded by that PR, carried into S3 as threat-model inputs: first sign-in and invite acceptance don't yet require a verified email (T-AUTH-04; invite acceptance still requires the invite token); and `check_revoked` adds a Firebase lookup per request, so an unreachable Firebase now yields 401.

#### S5a. AI summary quality and injection hardening — DONE 2026-10-21 (PRs #197–#205)

**Scope rule.** No new AI feature. This milestone hardens and measures the existing executive summary only (see R5).

Work:
1. **SDK migration.** Replace the deprecated `google-generativeai==0.8.3` with the current Google Gen AI SDK (`google-genai`). Confirm the model id and the structured-output API against the vendor docs on the day you implement. Keep the existing mock tests green first.
2. **Schema enforcement.** Pass `response_schema`, using the pydantic model the code already validates with. On validation failure, fall back to the deterministic template (`_build_fallback`). **Never fall back to raw model text.**
3. **Grounding.**
   - Each `notable_risks` item carries `finding_ids` drawn from the input.
   - A post-validator drops any item that cites an id not in the input and logs a count (no content).
   - ~~Put the EPSS and KEV values in the input.~~ _(2026-10-19: the summary input is the real aggregate `Finding`, not per-CVE data. Citations use `Finding.id`; a KEV finding is one with `source == "kev_vendor_match"` and severity `critical` or `high`, and the top-3 KEV findings are ranked by `severity_score`. EPSS and CVSS are not in the input and are out of S5a's scope. See `docs/ai/eval-protocol.md` §2 and §4.)_
   - Replace "never cite CVE ids" with "cite only ids present in the input".
4. **Injection hardening.**
   - Move `org.name`, `industry_label`, `employee_range` _(added 2026-10-19: also interpolated raw, `ai_summary.py:107`)_ and `primary_state` into a JSON data block serialised with `json.dumps`.
   - Add an instruction that the data block is data, not instructions.
   - Allow no raw interpolation anywhere in the prompt. This makes the README claim and the comment at `ai_summary.py:75-76` true.
5. **Timeout and budget.** A request timeout (proposed: 20 s) that leads to the fallback. Keep the 5/minute limit and document it as per process.
6. **Tests that run in CI, deterministic and with no network:**
   - prompt-construction tests: every org-supplied field appears only inside the data block, escaped;
   - output-validator tests: unknown ids are stripped; schema failure → template; timeout → template;
   - an injection corpus of at least 20 hostile org names and industry labels (instruction override, delimiter breakout, JSON breakout, Unicode tricks, long input), each asserting the prompt structure is intact.
7. **Live evaluation (manual or nightly, never a blocking CI gate).** ~~Run about 25 synthetic golden cases plus the injection corpus against the real model. Record the results in `docs/ai/eval-YYYY-MM-DD.md` with the model id, SDK version and date:~~
   - ~~schema-valid rate;~~
   - ~~citation-valid rate before the validator;~~
   - ~~KEV coverage (do the top-N KEV findings appear?);~~
   - ~~injection success rate, judged by a fixed rubric committed with the cases.~~

   ~~Check Gemini API pricing before the first run and cap the number of runs.~~

   _(Replaced 2026-10-19.)_ Follow [`docs/ai/eval-protocol.md`](ai/eval-protocol.md):
   - **Settings:** pinned in `eval_config.yaml`; production reads the same values.
   - **Dataset:** versioned `dataset/v1` with 27 dev and 22 held-out synthetic cases. The held-out split is never used for tuning.
   - **Runs:** B0 (as shipped, before any change), B1 (after the SDK migration only) and F (final), 3 repeats each. Raw responses and `usage_metadata` are committed.
   - **Metrics:** schema-valid, citation-valid before the validator, KEV coverage, injection success (canary tokens plus a fixed rubric), fallback/timeout/error rates, latency, and **cost per summary**.
   - **Reporting:** k/n with intervals; B1→F paired flips; failure examples in `docs/ai/failures-YYYY-MM-DD.md`.
   - **Harness:** bypasses the database last-good fallback.
   - **Spend:** a paid-tier key used for evaluation only, a budget alert, and a `--max-calls` guard.
8. **Deploy.** Declare `GEMINI_API_KEY` in `render.yaml` with `sync: false` (the value is set in the dashboard). Check on the Render dashboard whether the pilot has been serving the template.
9. **Fix the doc contradictions in the same PR:**
   - README: the injection claim (now true); the migration count (49 files, with 021 duplicated); "signed agent releases" → "release workflow exists, not yet run (S1)".
   - `docs/security/pii_inventory.md`: OpenAI → Gemini, and state that the org name is sent.
   - Repository description: drop "(Private)"; the repository is public.

**Acceptance.**
- `google-generativeai` is absent from every requirements file.
- `response_schema` is set.
- The validator, timeout and injection-corpus tests are green in CI.
- ~~One eval record is committed with all four numbers.~~ _(Replaced 2026-10-19.)_ The B0 (or a record of why it's unavailable), B1 and F runs are committed per the protocol: `run_meta.json`, raw responses, scores, and `runs/index.jsonl` with no undisclosed held-out runs. `docs/ai/eval-YYYY-MM-DD.md` reports every metric as k/n with an interval, the repeat range, the B1→F flips, and cost per summary.
- `docs/ai/failures-YYYY-MM-DD.md` is committed for B1 and F.
- `model_version` is the same across B1 and F, or the difference is flagged in the report.
- A test asserts that production's model id, temperature, thinking budget and timeout match `eval_config.yaml`.
- README, `pii_inventory.md` and the repository description match the code.
- `render.yaml` declares the key.

**Verification.**
```sh
git grep -n "google-generativeai" -- "*.txt" "*.toml" "*.lock"   # expect nothing
pytest backend/tests -q -k "ai_summary or injection or grounding"
gh repo view firegiant9000/Senior-Cybersecurity-Project --json description
```

**Evidence produced.** The tests, the corpus, the versioned dataset, the B0/B1/F run records, the eval report, the failures doc, the corrected docs.

**Resume potential.** "Hardened a Gemini-powered security briefing against prompt injection (JSON data isolation, a citation-required response schema, a grounding validator) and measured it with a pre-registered held-out protocol: 0 of 10 held-out injection attacks succeeded after the change versus 2 of 10 before (95% upper bound ≈ 30%; too few cases for a significance test), at +23% cost per summary." _(2026-10-19: the placeholders are filled only from the committed held-out F record, compared with B1, and worded per `docs/ai/eval-protocol.md` §5. If a difference isn't significant, the bullet says so, or leaves it out.)_

**Effort and cost.** ~~About 12–15 hours. A few dollars of API calls at most; pricing is not checked yet.~~ _(Revised 2026-10-19.)_ About 25–35 hours including the protocol. ~~About $2–3 of API calls at `gemini-2.5-flash` list prices checked 2026-10-19 (re-check on the day of the first run).~~ _(Revised 2026-10-20: `gemini-2.5-flash` is closed to new API keys, so S5a moved to `gemini-3.6-flash`; see `docs/ai/eval-protocol.md`.)_ About $8–12 of API calls across the protocol at 3.6-flash prices checked 2026-10-20, which double on 2027-01-01. The SDK migration also needed the framework part of S2 first (fastapi, starlette, pydantic, httpx), because `google-genai` requires newer versions.

**Interview questions.**
- Why does a schema not stop hallucinated content, and what does the citation check add?
- Why does the eval set live outside the blocking CI gate?
- How did you judge whether an injection succeeded?
- What is the blast radius if one succeeds, and why does that shape how much you invest?

#### S1. A real agent release: `agent-v0.1.0` with SBOM and provenance — DONE 2026-10-22 (PRs #222, #223)

Delivered:
- [Release `agent-v0.1.0`](https://github.com/firegiant9000/Senior-Cybersecurity-Project/releases/tag/agent-v0.1.0): linux/amd64 and arm64 binaries, one CycloneDX SBOM per binary, and `SHA256SUMS`.
- Keyless provenance and SBOM attestations through `actions/attest` (Sigstore, logged in Rekor). The GPG step and its secret references are gone (no signing secret was ever configured), and the workflow reads no secrets.
- `govulncheck` in binary mode on the built binaries blocks the release.
- The release is created as a draft, and the `verify` job checks the files a consumer downloads: checksums, `gh attestation verify` pinned to the workflow, the tag and GitHub-hosted runners, plus a tamper self-test that must fail. Only then does the release go public. The [verify job log](https://github.com/firegiant9000/Senior-Cybersecurity-Project/actions/runs/39733108283/job/119673019614) of the tag run shows each check.
- A `rehearse` dispatch runs build, draft and verify against a throwaway `0.0.0-dev` draft and deletes it afterwards. Only a real tag push undrafts.
- The consumer commands are in [`agent_release_verification.md`](security/agent_release_verification.md). The owner ran the quick-verify steps from a workstation against the published release, and they passed.

Changes from the plan below:
- The as-is tag was replaced by a dispatch dry run on `main`, so no broken `agent-v0.1.0` was ever published.
- `actions/attest` is used directly; `attest-build-provenance` and `attest-sbom` are now wrappers over it.
- The optional cosign signing was not added, because `gh attestation verify` already checks the same Sigstore bundle.

Work: tag `agent-v0.1.0` and let the existing workflow run once, as-is, to learn what breaks. Then replace the secret-dependent GPG step with **GitHub artifact attestations** (`actions/attest-build-provenance`, keyless, Sigstore-backed, no stored key) and optionally cosign keyless signing of the binaries; generate a **CycloneDX SBOM** for the agent (`cyclonedx-gomod` or syft) and attach it to the release, attested as well (`actions/attest-sbom`). Add a `verify` job that downloads the release asset and runs `gh attestation verify` against it. Fix the workflow's broken documentation path. Write `docs/security/agent_release_verification.md` with the exact commands a consumer runs.

**Acceptance.** A GitHub Release `agent-v0.1.0` exists with linux/amd64 and arm64 binaries, `SHA256SUMS`, a CycloneDX SBOM, and provenance attestations; `gh attestation verify` passes in a CI job and in the documented manual steps; no signing secret exists in the repository settings.

**Evidence produced.** The release page, the attestation, the SBOM file, the verify job log.

**Resume potential.** "Shipped the Hacker Tracker host agent with keyless build provenance (GitHub artifact attestations, Sigstore) and a CycloneDX SBOM, verifiable with `gh attestation verify`; replaced a secret-dependent GPG signing step."

**Interview questions.**
- What does a build provenance attestation prove, and what does it not prove?
- Why keyless signing instead of a stored GPG key? What is the trust root?
- What is in the SBOM, and how would a consumer use it after a new CVE drops?
- How would you detect that someone tampered with the release asset after publication?

**Follow-ups found during S1 (Firebase, outside S1's scope).** These came up on PR #222 on 2026-10-22:

- **What happened.**
  - The PR's preview deploy failed with a 403 on `serviceusage.services.get`.
  - The CI secret `FIREBASE_SERVICE_ACCOUNT` held a key for the `firebase-adminsdk` service account, which had lost (or never had) its Hosting permission. It passed the day before.
  - The fix was a dedicated `github-hosting-deploy` service account (Firebase Hosting Admin, API Keys Viewer, Service Usage Consumer) with a new key in that secret.

The follow-ups:

1. **Retire the old CI key.** The `firebase-adminsdk` key previously stored in `FIREBASE_SERVICE_ACCOUNT` is still active in Google Cloud.
   - First confirm which key ID the Render backend uses, so the production key isn't disabled.
   - Then delete the CI key.
   - Do this together with the Firebase Admin SDK key rotation already pending from the career audit (one key was exposed in pre-scrub history).
2. **Explain the permission change.** The Hosting deploy permission disappeared between 2026-10-21 21:46 UTC and 2026-10-22 05:04 UTC.
   - Check Cloud Audit Logs (`protoPayload.methodName="SetIamPolicy"`) for who changed the project's IAM policy, and when.
   - If nobody recognises the change, treat it as a security incident.
   - While there, act on the console's "excess permissions" recommendation for the four Editor accounts.
3. **Optional: remove the key altogether.** Replace the deploy key with Workload Identity Federation, so GitHub authenticates to Google with a short-lived OIDC token (the same trust model as S1), and no long-lived key lives in repo secrets.

#### S2. Dependency and supply-chain hardening — DONE 2026-10-21 (PRs #213–#218)

Delivered:
- Hash-locked backend requirements, with pytest and ruff removed from the production image.
- Blocking gates for pip-audit, govulncheck, npm audit (high and above, production dependencies), Trivy on the backend image, and CodeQL (Python, JavaScript/TypeScript, Go, Actions; `security-extended`).
- All 41 `uses:` references pinned to commit SHAs, with a CI grep that fails on an unpinned one.
- `permissions: contents: read` at the top of every workflow.
- Deploy secrets passed through `env:`.
- `alembic check` is blocking, after the models were aligned with the migrations.

Allowed exceptions, each with an expiry of at most 90 days, live in [`scan_exceptions.md`](security/scan_exceptions.md), and CI enforces the expiries. The list is empty at close-out.

Semgrep was evaluated and not kept: CodeQL found 0 alerts, and all 10 Semgrep findings were non-actionable. Making the gates required checks on `main` is a repository setting, which the owner applies.

Work: blocking CI gates for each language: **CodeQL** (Python, JavaScript/TypeScript, Go) on PR and weekly; **pip-audit** with a lockfile or hashes for the backend (introduce `requirements.lock` or `uv.lock`); **govulncheck** for the agent; **npm audit** at high severity for the frontend; **Trivy** on the backend image with CRITICAL and HIGH failing; **Semgrep** with a small curated ruleset if it catches something CodeQL does not (drop it if not). Pin every GitHub Action to a commit SHA; add a top-level `permissions: contents: read` to every workflow; move the Render deploy-hook secret out of shell interpolation. Upgrade the 2023-vintage backend pins (fastapi, starlette, pydantic, python-multipart, sqlalchemy) and Go to a supported version; fix what breaks. Remove pytest and ruff from the production requirements. Document allowed exceptions in `docs/security/scan_exceptions.md` with an expiry date for each. _(2026-10-18: S2 now runs right after S5a. Added:)_ make `alembic check` blocking by removing `continue-on-error`, or record in `scan_exceptions.md`, with an expiry date, why it can't be.

**Acceptance.** Five gates (CodeQL, pip-audit, govulncheck, npm audit, Trivy) are required on `main`; all green; every action pinned by SHA; every exception documented with an expiry; the pip Dependabot job passes.

**Evidence produced.** The workflow files, one green run of each gate, the exceptions document.

**Resume potential.** "Added blocking SAST, dependency-audit and container-scan gates (CodeQL, pip-audit, govulncheck, npm audit, Trivy) to a FastAPI, React and Go codebase, pinned every CI action to a commit SHA, and upgraded 6 out-of-date dependencies with published advisories."

**Interview questions.**
- Why pin Actions to SHAs rather than tags? What attack does it stop?
- When is a scanner exception acceptable, and how do you stop it becoming permanent?
- What is the difference between what CodeQL finds and what pip-audit finds?
- Why should test tooling not be in the production image?

#### S3. STRIDE threat model — DONE 2026-10-22 (#225)

Delivered: [`threat_model.md`](security/threat_model.md) holds 110 threats: 41 CONTROL, 21 TEST, 18 ACCEPTED and 30 OPEN (plus 1 withdrawn). `.github/scripts/check_threat_model.py` runs in the `security.yml` workflow and checks the classifications and evidence. Writing it surfaced 10 findings (see the document's Findings). One, an SSRF in the domain checks, was fixed in #224 before publication; none of the other nine was severe, and none of them was fixed in S3. The OPEN rows are scheduled for S4, S5 or owner action.

<a id="s3-privacy-page-follow-up"></a>Follow-up (2026-10-22): bring the in-app `/privacy` page (`frontend/src/pages/PrivacyPage.tsx`) in line with [`privacy.md`](security/privacy.md): the hosting region, and the Gemini and domain-lookup providers. Confirm the Render database region, then pin it in `render.yaml`.

Work: `docs/security/threat_model.md` covering agent enrollment, agent upload, token lifecycle and rotation, replay, human authentication (including the email-link fallback), organization tenancy, the global-admin boundary, the ingestion pipeline (NVD, KEV, EPSS), the outbound domain checks and the AI summary inputs. For every threat, one of: **CONTROL** (with the file and line), **TEST** (with the test name), **ACCEPTED RISK** (with the reason and owner), or **OPEN RISK** (with the milestone that closes it). The threat model drives S4 and S5: every OPEN RISK must map to a later item or be explicitly accepted.

**Acceptance.** Every threat row has exactly one classification; every TEST row names a test that exists; every OPEN RISK names a milestone; the document is linked from the README security section.

**Evidence produced.** The threat model document.

**Resume potential.** "Wrote a STRIDE threat model for Hacker Tracker's agent enrollment, upload, token lifecycle, tenancy and AI-input paths (110 threats), mapping each to a control, a test or an accepted risk, and used it to drive the authorization suite."

**Interview questions.**
- Walk me through the spoofing and tampering threats on the agent upload path and how each is controlled.
- Why is client-chosen `(scan_id, nonce)` weaker than a timestamped, signed request, and did you accept that?
- What is the global-admin boundary and why is cross-tenant access "by design" there?
- What threat did writing the model surface that you had not considered?

#### Owner actions: repo hardening

Settings the owner applies; none is a code change. Rows from the S3 threat model:
- T-REL-02: a tag ruleset protecting `agent-v*`.
- T-REL-03: immutable releases.
- T-CI-02: Environment-gated deploy secrets, or a keyless deploy.
- T-CI-04: `persist-credentials: false` on the remaining checkouts.
- T-CI-05: required Security, CodeQL and Secret-scan checks, required approvals, and Dependabot security updates.

#### S4. Authorization assurance

Work: a **route-enumerating authorization suite**. A test walks the FastAPI router, requires every route to appear in a classification table (`public`, `authenticated-global`, `organization-scoped`, `agent`, `administrator`), and fails CI on any unclassified route. For organization-scoped routes it issues requests as a member of org B against org A's resources and expects 403 or 404 (never 200, never 500). It also tests member vs admin on admin-only routes, a revoked agent token, an expired rotated token past its grace, a replayed upload, and the public endpoint boundary. These tests use **real token verification**: Firebase emulator or a locally signed test key with the real verification code path, not the autouse mock. Add security headers middleware (and a `headers` block in `firebase.json`), a body-size limit on the agent upload route, and a `/health` that checks the database.

Threat-model rows: T-PLAT-06, T-ENR-04, T-UPL-09, T-TOK-07, T-TOK-08, T-AUTH-04, T-AUTH-07, T-TEN-05, T-TEN-07, T-TEN-10, T-TEN-12, T-DOM-09, T-PLAT-01, T-PLAT-09. The suite, headers and `/health` above cover T-AUTH-07, T-TEN-12, T-TOK-07, T-PLAT-01 and T-PLAT-09. The rest need their own fixes:
- A body-size limit on the agent upload route, applied app-wide with a pre-read check on file uploads (T-PLAT-06).
- Revoked agent token: rotate only active rows; never move `revoked_at` later (T-ENR-04), and revoking an agent covers its rotation chain (T-TOK-08).
- Require `email_verified` on account auto-create and on invite acceptance (T-AUTH-04).
- Org-role checks on the destructive routes that only check membership (T-TEN-05).
- Decide and enforce owner-only admin grants (T-TEN-07).
- Close the gap where the analytics event route doesn't bind events to the caller's org (T-TEN-10).
- HTTPS-only check on the agent's `--server` URL, with HSTS from the headers work (T-UPL-09).
- Egress guard regression tests: pin the real HTTP client's `follow_redirects=False`, and test a redirect to a non-default port (T-DOM-09).

**Progress.** Stage A (harness, real verification, route table: 128 routes: public 11, authenticated-global 29, organization-scoped 76, agent 2, administrator 10; 5 behind the M365 flag) — PR #226. Stage B (cross-tenant sweep over 76 organization-scoped routes; T-TEN-10 fixed) — PR #227. Stage C (role rules: owner-only admin management, org admin on 7 destructive routes, verified email for sign-up and invites) — PR #228. S4 is not done.

**Acceptance.** Unclassified routes: 0. Cross-tenant leaks: 0. Routes returning 500 on a denied request: 0. The suite runs with the autouse auth mock disabled. The classification table is committed and counted.

**Evidence produced.** The suite, the classification table, a CI run showing the route count.

**Resume potential.** "Built a route-enumerating authorization suite over [N] API endpoints that fails CI on any unclassified route and verifies cross-tenant isolation with real token verification; found and fixed [K] mis-scoped or unclassified routes and added security headers and an upload body limit."

**Interview questions.**
- How does the suite guarantee a new route cannot ship unclassified?
- Why does a cross-tenant test with a mocked verifier prove less than one with real verification?
- 403 or 404 for a cross-tenant read? Why?
- How do you test token rotation grace without sleeping?

#### S5. DAST and manual AppSec

Work: **OWASP ZAP baseline** against the docker-compose stack in CI, failing at medium and above once the header work in S4 lands. ~~Harden the AI summary prompt: delimit and escape org-supplied fields, add a prompt-injection test corpus, validate output against the schema.~~ _(Moved to S5a on 2026-10-18.)_ If pursuing BSCP, perform a **manual Burp assessment** of the API and record each finding as: finding, risk, exploit path, fix, regression test.

Threat-model rows: T-ING-04, T-ING-06, T-ING-07, T-ING-10, T-DOM-08, T-AI-09, T-PLAT-03, T-PLAT-05, T-PLAT-07, T-PLAT-10, T-PLAT-13.

Threat-model fixes (from the OPEN rows in [`threat_model.md`](security/threat_model.md)):
- Validate ingested EPSS values (within [0, 1], only for requested CVEs) (T-ING-04).
- Explicit timeouts and response-size caps on feed fetches (T-ING-06).
- Mark a run partial when EPSS batches fail or NVD returns 429 (T-ING-07).
- Send the NVD key as a header on every path (T-ING-10).
- Domain-check follow-ups from #224: try every resolved address, validate `primary_domain` on write, and test that the body read stops at the cap (T-DOM-08).
- Per-user or per-org quota on AI summary `force_refresh` (T-AI-09).
- Fail closed when `APP_ENV` is unset, and reject wildcard, IP and `http://` origins in production (T-PLAT-03).
- Rate-limit storage and client identity need hardening (shared store, trusted client identity, limits on data-lifecycle routes) (T-PLAT-05).
- An error-message policy and a global exception handler (T-PLAT-07).
- Log scrubbing and an access-log policy (T-PLAT-10).
- Validate the characters of the request id (T-PLAT-13).

**Acceptance.** ZAP baseline green at medium and above on every PR; ~~the injection corpus runs in CI~~ (moved to S5a, 2026-10-18); if the Burp assessment is done, `docs/security/assessment-YYYY-MM.md` exists with every finding closed by a regression test or accepted.

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
