# S2: Dependency and supply-chain hardening — design

Date: 2026-10-20. Owner: Arlo Kharod. Roadmap: `docs/PRODUCT_VIABILITY_ROADMAP.md`, milestone S2.

## Intent

S2 has two purposes, in this order:

1. **Portfolio evidence.** A credible "AppSec/DevSecOps reference implementation" story: blocking SAST, dependency-audit and container-scan gates, SHA-pinned Actions, least-privilege workflow tokens, and a scanner-exception process that cannot quietly become permanent. The roadmap's résumé line and four interview questions (S2 section) are the bar.
2. **Real protection for the pilot.** The backend runs on Render for a real pilot org. The gates must catch real problems, not just exist.

## Goals

- Five blocking gates on every PR into `main`: **CodeQL** (Python, JS/TS, Go; also weekly), **pip-audit**, **govulncheck**, **npm audit** (`--audit-level=high`), **Trivy** on the backend image.
- A hash-pinned lockfile for the backend; production image installs with `--require-hashes`.
- Test and lint tools (pytest, pytest-asyncio, ruff) out of the production install.
- Remaining 2023-era backend pins upgraded (at least python-multipart, sqlalchemy; plus anything else with a published advisory), Go moved to a supported release. Fix what breaks.
- Every `uses:` in every workflow pinned to a full commit SHA with the tag in a trailing comment.
- Top-level `permissions: contents: read` on every workflow, widened per job only where needed.
- No secret interpolated into a `run:` script via `${{ secrets.* }}`; pass through `env:`.
- `alembic check` either blocking, or a dated exception explaining why not.
- `docs/security/scan_exceptions.md` with an enforced expiry on every entry.
- The pip Dependabot job passes.
- Roadmap housekeeping: S5a marked DONE, S5a résumé placeholders filled.

## Non-goals

- Agent release signing, SBOM, provenance: that is S1. S2 only pins Actions and tightens permissions in `agent-release.yml`; it does not change its signing logic.
- Python major/minor upgrade. Stay on 3.11 (supported to 2027-10).
- Re-doing PR #200's upgrades (fastapi 0.133, starlette 1.3.1, pydantic 2.12.5, httpx 0.28.1, sentry-sdk 2.56). Don't touch those pins except as a lockfile resolution requires.
- The S5a eval. Don't re-run it or spend on Gemini.
- Changing Dependabot's monthly grouping policy.

## Anti-goals (would be a failure even if CI is green)

- A gate that is green because it was configured not to look: `continue-on-error`, blanket ignores, `|| true`, scanning the wrong directory, audit levels lowered to pass.
- An exception without an expiry, or an exception list that nothing checks.
- Breaking the Render deploy or the pilot (a lockfile the Docker build can't install, a dependency upgrade that changes API behaviour unnoticed).
- Overstated claims. Counts in PR bodies and the roadmap come from actual scanner output.

## Decisions made (by Arlo, 2026-10-20)

- **Lockfile: pip-tools.** `backend/requirements.in` (direct production deps) compiles to `backend/requirements.txt` with `--generate-hashes`. `backend/requirements-dev.in` (`-c requirements.txt` plus pytest, pytest-asyncio, ruff, pip-audit if wanted locally) compiles to `backend/requirements-dev.txt` with hashes. The file name `requirements.txt` stays because the Dockerfile, Render (Docker build) and Dependabot already use it. Dockerfile: `pip install --no-cache-dir --require-hashes -r requirements.txt`. CI jobs that run tests or ruff install both files.
- **Semgrep: trial, keep only if useful.** Run Semgrep once (a small curated ruleset, e.g. `p/python`, `p/typescript`, `p/golang`, `p/secrets` or similar) against `main` alongside the CodeQL results. Record in the stage C PR what Semgrep found that CodeQL didn't. If it found nothing unique and actionable, don't add it to CI and say so in `docs/security/scan_exceptions.md` or the PR. If it did, add it as a blocking job with that ruleset.
- **Branch protection: Arlo applies it.** The builder delivers the exact list of required check names (as they appear in the GitHub UI) after each gate has a green run on `main`. No repository-settings or branch-protection change is made by the builder.

## Builder's calls already made (Claude's, open to Arlo's correction)

- **Trivy fails on CRITICAL and HIGH with a fix available** (`--ignore-unfixed`, `--severity CRITICAL,HIGH`, `--exit-code 1`). Unfixed findings are printed in the job log (a second non-blocking Trivy step, or table output) but don't block, or the Debian base image is red indefinitely. Scan the image built from `backend/Dockerfile` in CI (build, don't push).
- **Exception policy.** `docs/security/scan_exceptions.md` holds one table row per exception: ID (CVE/GHSA/rule id), scanner, package/location, reason, compensating control or "none", added date, **expiry date at most 90 days after added**. A small script (Python, stdlib only, in `scripts/` or `.github/scripts/`) parses the table and fails CI if any expiry is in the past or more than 90 days after its added date. Each scanner's ignore mechanism (`.trivyignore`, `pip-audit --ignore-vuln`, CodeQL dismissal, npm overrides) must reference only IDs listed in the document; the script checks this for the file-based ones (`.trivyignore`, pip-audit ignore list). The script has its own small test.
- **Delivery: stages A1, A2, B, C, D, E, each a PR against `main`, opened after the previous one merges** (CI only runs on PRs into `main`, and CI changes must be proven on CI). Stage order below.
- **Go version:** the newest Go release that is supported on the day of implementation (check go.dev/doc/devel/release); set it in `agent/go.mod` and every `setup-go` step (`ci.yml`, `agent-release.yml`). The agent is stdlib-only, so this is mostly a toolchain bump.
- **Node stays on 20** unless npm audit forces otherwise (check Node 20's support status on the day; if EOL, bump to the current LTS and note it).

### Settled after the builder review (Claude's calls unless marked)

- **CodeQL setup.** Default setup is `not-configured` (checked 2026-10-20 via `gh api …/code-scanning/default-setup`), so an advanced `codeql.yml` workflow is free to upload SARIF.
- **What "CodeQL blocking" means.** Use the code-scanning check that CodeQL results produce on PRs, which fails on **new** alerts introduced by the PR, not on the existing backlog. Arlo makes it required through branch protection or a ruleset (stage E). There is no in-workflow `gh api` alert query. The existing backlog is triaged in stage C: fix it, or dismiss it with a reason that is recorded in `scan_exceptions.md`.
- **Drift on a floating base or new advisories.** Every audit gate (pip-audit, govulncheck, npm audit, Trivy) also runs weekly on `main` (`schedule:`), so drift shows up on `main` first. The base image is pinned by digest (`python:3.11-slim@sha256:…`), and Dependabot's docker ecosystem keeps the digest current. When a gate goes red on a PR for an unrelated new advisory, the response is to upgrade or bump the base if a fix exists, and otherwise to add an exception. Either can go in the PR or in a small separate PR.
- **Go platforms.** The agent ships for linux/amd64 and linux/arm64 only. Current Go supports Linux kernel 2.6.32 and later (3.2 and later from Go 1.24), which covers any supported distro, so the bump doesn't change supported platforms.
- **Lock compilation.** Compile both lockfiles inside a `python:3.11-slim` Linux container, not on Windows, so markers and hashes match the image. Render's only other use of the image is `preDeployCommand: sh /app/scripts/migrate.sh`, which runs inside the same image. Grep the repo for other `requirements.txt` consumers (scripts, docs, eval tooling) and point them at the dev file where they need test tools.
- **npm audit scope.** The blocking step is `npm audit --omit=dev --audit-level=high`, covering the code that ships to browsers. A second, non-blocking step runs the full audit (dev dependencies included) and prints the findings. Plain `npm audit` has no ignore mechanism, so a dev-only finding without a fix would otherwise block forever. No `audit-ci`, and no other new tool.
- **Semgrep trial.** A throwaway run on a branch (or a local run), with the results summarised in the stage C PR. No workflow is committed unless Semgrep is kept.
- **Dependabot evidence.** After stage A merges, Arlo (or the builder via `gh`, if the API allows) triggers the pip Dependabot update. Acceptance is a successful run. Fixing the root cause may include a `dependabot.yml` change, as long as the monthly grouping stays the same.

## Stages

Each stage: its own branch off fresh `origin/main`, gate passes locally, one `reviewer-risk` review (at most 2 fix rounds), PR for Arlo. Arlo merges.

### A. Lockfile, dependency upgrades, roadmap housekeeping

**Split into two PRs (Arlo, 2026-10-20), because each merge auto-deploys to the pilot:**
- **A1 (no behaviour change):** lockfile and dev split at the *current* versions, the pyproject cleanup, the Dockerfile `--require-hashes` change, the CI install changes, and the roadmap housekeeping. Transitive pins in the lock stay at what the current image resolves to (`pip freeze` from today's image) wherever possible.
- **A2 (upgrades):** python-multipart, sqlalchemy, other advisory-driven bumps, and the Go bump.

A Render rollback (dashboard) is the recovery path for either one.

- Create `requirements.in` and `requirements-dev.in`, compile both with hashes. Move pytest, pytest-asyncio and ruff to the dev file.
- (A2) Upgrade python-multipart, sqlalchemy, and any other direct dependency with a published advisory (run pip-audit locally against the new lock to find them). Leave PR #200's pins alone.
- Remove the stale `[tool.poetry.dependencies]` section (and poetry build-system) from `backend/pyproject.toml`, keeping the `[tool.pytest…]`, `[tool.ruff…]` and `[tool.pylint…]` config. It lists `psycopg2-binary`, `pytest` and old ranges that no longer match reality and is a likely cause of the failing Dependabot pip job. Confirm the actual Dependabot failure reason first (Insights → Dependency graph → Dependabot, or the job log) and fix that.
- Dockerfile installs with `--require-hashes`. CI test/lint jobs and `matcher-regression.yml` install `requirements.txt` and `requirements-dev.txt`.
- Go: bump to the supported release (go.mod and setup-go).
- Roadmap: S5a heading → "DONE 2026-10-21 (PRs #197–#205)"; fill the S5a résumé placeholders from PR #203's body draft line, per `docs/ai/eval-protocol.md` §5.
- Verify the production image builds and starts locally (`docker build`, then `/health`), because Render will build it on merge.

### B. pip-audit, govulncheck, npm audit as blocking jobs; exceptions document

- New jobs (in `ci.yml` or a new `security.yml`, builder's choice; one clear job name per gate). pip-audit runs against the hashed `requirements.txt` (`pip-audit -r requirements.txt --require-hashes` or equivalent, no install of the app needed). govulncheck on `agent/`. npm audit in `frontend/` per "npm audit scope" above. All four gates also run on a weekly schedule.
- Create `docs/security/scan_exceptions.md` and the expiry-check script with its test, wired into CI as a blocking step.
- Triage day-one failures: upgrade first; exception (with expiry) only where no fixed version exists or the fix is a breaking major that needs its own work. Report counts found / fixed / excepted in the PR body.

### C. CodeQL and Trivy; Semgrep trial

- CodeQL via `github/codeql-action` for `python`, `javascript-typescript`, `go`, on `pull_request` to `main`, `push` to `main`, and a weekly schedule. Default query suite unless security-extended is cheap enough to keep green; record which. Go needs a build (autobuild or `go build ./...`).
- Make CodeQL blocking: the job fails on any open alert of severity error/high in the PR's results (via the action's upload plus a check, or branch protection on the "CodeQL" code-scanning check, which Arlo would set). Builder picks the mechanism and documents it; triage existing alerts as for stage B.
- Trivy image job as described under "Builder's calls".
- Semgrep trial as described under "Decisions made".

### D. Workflow hardening

- Pin every `uses:` in all workflows (`ci.yml`, `secret-scan.yml`, `agent-release.yml`, `matcher-regression.yml`, plus the new ones) to a full commit SHA, with `# vX.Y.Z` comment. Resolve SHAs from the action's tag via `gh api`, not from memory. Dependabot's github-actions ecosystem keeps SHA pins updated.
- Top-level `permissions: contents: read` everywhere; per-job widening only where needed (deploy-preview: checks/pull-requests write; agent-release: `contents: write` moved to the job; CodeQL: `security-events: write`).
- Secrets out of `run:` interpolation: `deploy-backend` (`RENDER_DEPLOY_HOOK_URL`), the Sentry config check in `deploy-frontend` (`SENTRY_AUTH_TOKEN`, `SENTRY_PROJECT`), and `post-deploy-healthcheck` (`BACKEND_URL`). Pass via `env:` and reference `"$VAR"`.
- `alembic check`: remove `continue-on-error` if the drift can be fixed with a forward-only migration in reasonable effort; otherwise leave it advisory and add a dated exception entry explaining the drift items and the follow-up. Builder judges the effort and states it in the PR; a migration that touches production data needs Arlo's OK first. _(Outcome, 2026-10-21, PR #217: the 18 drift items were all on the model side and were fixed by aligning the models to the migrations, with no migration and no data change. `alembic check` is now blocking; the advisory path was not needed.)_

### E. Close-out

- Once every gate has a green run on `main`: give Arlo the exact required-check names for branch protection.
- Roadmap S2 marked done, résumé placeholder `[N]` filled from the actual count of upgraded dependencies with published advisories (from stage A/B triage records).
- Obsidian notes updated with anything non-obvious.

(The handoff's stage "E: mark S5a done" rides with stage A, as above.)

## Constraints

- Public repo: no secrets in commits, PR bodies, logs or the vault.
- Gate per stage: backend `ruff check` + `ruff format --check` + pytest on Postgres (baseline 1131 passed, 8 known AsyncMock warnings); frontend ESLint + `tsc` + Vitest (baseline 466 passed); agent `go vet` + gofmt + `go test`. Report counts against the baseline.
- DB migrations forward-only.
- No new third-party Go modules in the agent.
- Builder never merges, deploys, closes PRs or changes repo settings.

## Left to the builder

- Workflow file layout (extend `ci.yml` vs a new `security.yml`) and job names, as long as each gate is one clearly named check.
- Exact Semgrep rulesets for the trial; CodeQL query suite.
- Which extra dependencies to upgrade beyond the named ones, guided by pip-audit output.
- Exception-checker script location and format details, within the policy above.

## Acceptance (from the roadmap, unchanged)

Five gates (CodeQL, pip-audit, govulncheck, npm audit, Trivy) are required on `main`; all green; every action pinned by SHA; every exception documented with an expiry; the pip Dependabot job passes.
