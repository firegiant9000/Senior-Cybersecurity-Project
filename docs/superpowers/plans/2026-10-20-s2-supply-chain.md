# S2 Supply-Chain Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hash-locked backend dependencies, five blocking security gates (pip-audit, govulncheck, npm audit, CodeQL, Trivy), SHA-pinned least-privilege workflows, and an exception list whose expiries CI enforces.

**Architecture:** pip-tools compiles `requirements.in`/`requirements-dev.in` into hashed lockfiles. A multi-stage Dockerfile ships production deps only, and a `dev` stage adds test tools for docker-compose. The new gates live in `.github/workflows/security.yml` (audits, Trivy, exception check) and `.github/workflows/codeql.yml`. `docs/security/scan_exceptions.md` is the single source of suppressed IDs: a stdlib script validates expiries and emits the per-scanner ignore lists that CI feeds to the scanners.

**Tech Stack:** pip-tools, pip-audit, govulncheck, npm audit, github/codeql-action, aquasecurity/trivy-action, GitHub Actions, Python 3.11 stdlib (unittest).

**Spec:** `docs/superpowers/specs/2026-10-20-s2-supply-chain-design.md`. Read it first; this plan doesn't repeat its rationale.

## Global Constraints

- Python stays **3.11**. Don't touch PR #200's pins (fastapi 0.133.0, starlette 1.3.1, pydantic 2.12.5, httpx 0.28.1, sentry-sdk 2.56.0, google-genai 2.31.0) unless resolution forces it, and say so if it does.
- Lockfiles are compiled **inside a `python:3.11-slim` container** (linux/amd64), never on Windows.
- Trivy: `--severity CRITICAL,HIGH --ignore-unfixed --exit-code 1`.
- npm audit blocking: `npm audit --omit=dev --audit-level=high`. Full audit is non-blocking.
- Exception expiry: **at most 90 days** after the added date. An entry is valid through its expiry date (inclusive).
- Each stage (A1, A2, B, C, D) is its own branch off fresh `origin/main`, opened as a PR after the previous one merges. Arlo merges. No repo-settings or branch-protection changes.
- New workflow steps are SHA-pinned from creation (`uses: owner/repo@<40-hex> # vX.Y.Z`). Resolve SHAs with `gh api`, never from memory.
- No new third-party Go modules. No new npm tooling (no `audit-ci`).
- Commits: `git -C <worktree> -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`. No Claude attribution. One shell command per Bash call.
- Gate per stage (report counts vs baseline):
  - backend `ruff check app tests evals`, `ruff format app tests evals --check`, and pytest on Postgres (baseline **1131 passed**, 8 known AsyncMock warnings);
  - frontend `npm run lint`, `npx tsc --noEmit` and `npm test` (baseline **466 passed**);
  - agent `go vet ./...`, `gofmt -l .` (empty) and `go test ./...`.
- Public repo: no secrets in commits, PR bodies, logs or the Obsidian vault.

## Review Focus

1. **Render builds the hashed lock on linux/amd64.** A wheel or marker missing on that platform fails the pilot deploy at merge. Owned by Task 2: `docker build --platform linux/amd64`, then `/health` on the built image.
2. **Local dev after pytest leaves the prod image.** `make test` and `make backend-lint` run `docker compose exec backend pytest|ruff`. Owned by Task 2: the compose `backend` service uses `target: dev`, and the test checks that pytest is present in `dev` and absent in the final stage.
3. **A gate that's green because it isn't looking** (wrong directory, zero packages, ignore list swallowing everything). Owned by Tasks 9 and 12: each gate gets one deliberate red run on the PR branch from a known-vulnerable canary, which is then reverted, and the PR links the red run.
4. **The expiry boundary and malformed rows.** "Expires today" passes, "expired yesterday" fails, and a bad date or unknown scanner fails rather than being skipped. Owned by Task 8's unit tests.
5. **Dependabot PRs and the new gates.** Dependabot PRs get no repo secrets, and the monthly grouped PR must pass every new gate without them. Owned by Tasks 9 and 11: no gate job reads a secret, and the CodeQL job gets `security-events: write` through its job `permissions:`.

---

## Stage A1: lockfile and dev split at current versions (branch `feat/s2-a-lockfile`, worktree `C:\dev\ht-s2-a`, already created)

The branch tracks `origin/main` as upstream. Push with `git push -u origin feat/s2-a-lockfile`.

### Task 1: Find out why the Dependabot pip job fails

**Files:** none (read-only). The finding goes in the A1 PR body.

- [ ] **Step 1:** `gh run list -R firegiant9000/Senior-Cybersecurity-Project --workflow "Dependabot Updates" --limit 20`. Dependabot runs as Actions runs. Pick the latest failed pip run.
- [ ] **Step 2:** `gh run view <id> -R firegiant9000/Senior-Cybersecurity-Project --log-failed`. Record the error class in one line, e.g. "poetry section in pyproject.toml unresolvable" or "pip resolver conflict X".
- [ ] **Step 3:** If the cause isn't the `[tool.poetry]` section, or isn't fixed by Task 2's changes, write down the extra fix needed and add it to Task 2. If no run is visible, ask Arlo to paste the error from Insights → Dependency graph → Dependabot.

### Task 2: Hashed lockfiles, dev split, multi-stage Dockerfile

**Files:**
- Create: `backend/requirements.in`, `backend/requirements-dev.in`, `backend/requirements-dev.txt`
- Modify (regenerated): `backend/requirements.txt`
- Modify: `backend/pyproject.toml` (delete `[tool.poetry]`, `[tool.poetry.dependencies]`, `[build-system]`; keep the pytest/ruff/pylint tool sections)
- Modify: `backend/Dockerfile`, `docker-compose.yml:21-24`
- Modify: `.github/workflows/ci.yml` (backend-lint and backend-test install steps), `.github/workflows/matcher-regression.yml:43`
- Modify: `Makefile:101`, `scripts/test-backend.sh:8`, `scripts/README.md:37`, `backend/scripts/README.md:22`, `docs/COMMANDS.md:38`, `docs/SETUP.md:108,212,237`. Anything that runs tests or ruff installs `requirements-dev.txt`.

**Interfaces:**
- Produces: `requirements.txt` (prod, hashed, pip-compile header) and `requirements-dev.txt` (hashed, compiled with `-c requirements.txt`, so shared pins are identical). Dockerfile stages `base` (prod deps), `dev` (base plus dev deps) and a final unnamed-target production stage that is **last in the file**, so Render's default build stays production. Later stages (B, C) audit `requirements.txt` and scan the default build target.

- [ ] **Step 1: Capture today's resolved set.** Build the current image, then run `docker run --rm <img> pip freeze` and save the output to the scratchpad as `freeze-b950844.txt`.
- [ ] **Step 2: Write `requirements.in`.** It holds today's direct pins minus `pytest`, `pytest-asyncio` and `ruff`, with the same specifiers (`greenlet>=3.0.0` stays a range). `requirements-dev.in` starts with `-c requirements.txt`, then `pytest==7.4.3`, `pytest-asyncio==0.21.1` and `ruff==0.1.11` (same versions; A2 may bump them).
- [ ] **Step 3: Compile inside `python:3.11-slim`** with the backend dir mounted. Use `pip install pip-tools`, then `pip-compile --generate-hashes --allow-unsafe --strip-extras -o requirements.txt requirements.in` (add `-c freeze-b950844.txt` so transitive pins equal today's), then the same for dev. Remove the temporary `-c freeze…` from the header comment if it leaks in, because Dependabot re-runs the header command.
- [ ] **Step 4: Diff the locks against the freeze.** Every package in the freeze, except pytest, pytest-asyncio, ruff, iniconfig, pluggy and packaging (if packaging is dev-only), must appear in `requirements.txt` at the same version. Expected: no version differences. Explain any that remain in the PR body.
- [ ] **Step 5: Dockerfile.**
  - `FROM python:3.11-slim AS base` installs prod with `pip install --no-cache-dir --require-hashes -r requirements.txt`.
  - `FROM base AS dev` copies and installs `requirements-dev.txt` with `--require-hashes`.
  - The final stage is `FROM base`, with the app copy, the non-root user and the CMD as today.
  - Keep the apt step in `base`.
  - Set `target: dev` on the compose backend service.
- [ ] **Step 6: Verify the production image.** `docker build --platform linux/amd64 -t ht-backend:a1 backend` succeeds. `docker run --rm ht-backend:a1 python -c "import pytest"` fails with ModuleNotFoundError. `docker run --rm ht-backend:a1 ruff --version` fails. Start the container with dummy env (APP_ENV=development, a dummy DATABASE_URL; copy the env names from `render.yaml`, no real values) and `curl localhost:8000/health` returns 200.
- [ ] **Step 7: Verify the dev image.** `docker build --target dev -t ht-backend:dev backend`, then `docker run --rm ht-backend:dev pytest --version` prints 7.4.3.
- [ ] **Step 8: Update the CI and doc installs** listed under Files to `pip install -r requirements.txt -r requirements-dev.txt`. Leave `cache: pip` as is.
- [ ] **Step 9: Run the backend gate.** In a venv with both files installed, run `ruff check app tests evals`, then `ruff format app tests evals --check`, then `pytest tests/` with `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cyber_threat_test_db` and `APP_ENV=testing` (run migrations first: `alembic -c app/db/alembic.ini upgrade head`). Expected: 1131 passed, 8 warnings.
- [ ] **Step 10: Commit.** Message: `build(backend): hash-locked requirements via pip-tools; test tools out of the production image`.

### Task 3: Roadmap housekeeping

**Files:** Modify `docs/PRODUCT_VIABILITY_ROADMAP.md:85` and `:148`

- [ ] **Step 1:** Change the line 85 heading to `#### S5a. AI summary quality and injection hardening — DONE 2026-10-21 (PRs #197–#205)`.
- [ ] **Step 2:** Run `gh pr view 203 -R firegiant9000/Senior-Cybersecurity-Project --json body`, find the draft résumé line, and replace the line 148 bullet with it. Keep the bracketed 2026-10-19 note and follow `docs/ai/eval-protocol.md` §5. If the draft omits a non-significant metric, so does the bullet.
- [ ] **Step 3: Commit.** Message: `docs(roadmap): mark S5a done and fill its resume line`.

### Task 4: Review and PR (A1)

- [ ] **Step 1:** Dispatch one `reviewer-risk` on `git diff origin/main...HEAD` with the spec and this plan's A1 section. Fix, then re-review (`model: haiku` for a small fix diff). At most 2 fix rounds.
- [ ] **Step 2:** Run `gh auth status` (firegiant9000 active), then `git push -u origin feat/s2-a-lockfile`.
- [ ] **Step 3:** Run `gh pr create --base main` with a body that covers:
  - the Dependabot root cause (Task 1);
  - the freeze diff result;
  - the image checks (prod has no pytest, `/health` returns 200);
  - the gate counts;
  - a note that the merge auto-deploys to Render, with no expected behaviour change and Render rollback as the recovery path.
- [ ] **Step 4:** Stop. Tell Arlo the PR is up. After the merge, ask Arlo to trigger the pip Dependabot update (or do it via `gh` if possible) and record the run result.

## Stage A2: upgrades (branch `feat/s2-a2-upgrades` off `origin/main` after A1 merges, new worktree `C:\dev\ht-s2-a2`)

### Task 5: Advisory-driven Python upgrades

**Files:** `backend/requirements.in`, `backend/requirements-dev.in`, both lockfiles, plus code fixes as needed.

- [ ] **Step 1: Baseline audit.** In a `python:3.11-slim` container, run `pip install pip-audit`, then `pip-audit -r requirements.txt --require-hashes --disable-pip` and the same for `requirements-dev.txt`. Save the output to the scratchpad. This is the "[N] with published advisories" evidence.
- [ ] **Step 2: Bump.** python-multipart and sqlalchemy go to their latest releases. Every other package pip-audit flagged goes to the lowest fixed version or later; take the latest patch of that minor. Bump pytest and pytest-asyncio and ruff to current. Bumping ruff to current will reformat and re-lint; keep that in its own commit.
- [ ] **Step 3: Recompile** both locks in the container, without the freeze constraint. Run pip-audit again; expected: no findings. Anything left over goes in the A2 PR body as a stage B exception candidate.
- [ ] **Step 4: Run the backend gate**; fix what breaks. Watch for:
  - SQLAlchemy 2.0.x deprecation warnings becoming errors;
  - pytest-asyncio ≥0.23 changing event-loop scope (the `asyncio_mode = "auto"` config in pyproject and the `conftest.py` fixtures);
  - python-multipart's import name (`python_multipart`) in newer versions.

  Report the counts against 1131.
- [ ] **Step 5:** Rebuild the prod image, check `/health`, and repeat Task 2 Step 6.
- [ ] **Step 6: Commit** in logical pieces: deps, then the ruff reformat, then test or code fixes.

### Task 6: Go to a supported release

**Files:** `agent/go.mod`, `.github/workflows/ci.yml` (agent job setup-go), `.github/workflows/agent-release.yml` (setup-go)

- [ ] **Step 1:** Check https://go.dev/doc/devel/release for the newest supported minor `1.N`.
- [ ] **Step 2:** Set `go 1.N.0` in `go.mod`. In both setup-go steps set `go-version: "1.N"` with `check-latest: true`, so CI always gets the newest patch. A `.0` toolchain would trip govulncheck on stdlib fixes.
- [ ] **Step 3:** Run the agent gate locally (`go vet ./...`, `gofmt -l .` empty, `go test ./...`, `go build ./cmd/hacker-tracker`).
- [ ] **Step 4: Commit.**

### Task 7: Review and PR (A2)

Same as Task 4. The PR body lists every bumped package (old → new, with the advisory ID where there is one) and the gate counts, and repeats the auto-deploy and rollback note.

## Stage B: audit gates and the exception list (branch `feat/s2-b-audit-gates`)

### Task 8: Exception document and checker

**Files:**
- Create: `docs/security/scan_exceptions.md`
- Create: `.github/scripts/scan_exceptions.py`
- Test: `.github/scripts/test_scan_exceptions.py` (stdlib `unittest`, so the job doesn't need the backend deps)

**Interfaces (produces):**
- Document format: a `## Exceptions` heading followed by a markdown table with exactly these columns: `| ID | Scanner | Package / location | Reason | Compensating control | Added | Expires |`. Scanner is one of `pip-audit`, `npm-audit`, `govulncheck`, `trivy`, `codeql`, `semgrep`, `alembic-check`. Dates are `YYYY-MM-DD`. Above the table, policy prose: the 90-day maximum, that renewing means a new Added date and a fresh justification, upgrading first, and that npm/govulncheck/codeql entries are recorded here but suppressed by other means (npm `overrides`, a CodeQL dismissal whose comment cites the ID).
- `@dataclass(frozen=True) class ScanException: id: str; scanner: str; location: str; reason: str; control: str; added: date; expires: date`
- `parse_exceptions(markdown: str) -> list[ScanException]`. Raises `ValueError` naming the row for a malformed row, bad date or unknown scanner.
- `validate(entries: list[ScanException], today: date) -> list[str]`. Returns error strings: expired (`expires < today`), window too long (`expires - added > 90 days`), or `expires < added`.
- `active_ids(entries, scanner: str, today: date) -> list[str]`. Unexpired IDs for one scanner.
- CLI: `python .github/scripts/scan_exceptions.py check [--file PATH]` exits 1 on parse or validate errors and prints them. `python .github/scripts/scan_exceptions.py ids <scanner> [--file PATH]` prints one ID per line. The default file is `docs/security/scan_exceptions.md`, and today is the UTC date.

- [ ] **Step 1: Write the failing tests.**
  - `test_empty_table_is_valid`
  - `test_expires_today_is_valid` (today = expires)
  - `test_expired_yesterday_fails`, where the error contains the ID
  - `test_window_over_90_days_fails`: added 2026-10-20 with expires 2027-01-19 (91 days) fails, and with 2027-01-18 (90 days) passes
  - `test_expires_before_added_fails`
  - `test_bad_date_raises`
  - `test_unknown_scanner_raises`
  - `test_active_ids_filters_scanner_and_expiry`: two trivy entries, one expired, plus one pip-audit entry; `active_ids(..., "trivy", today)` returns only the unexpired trivy ID
  - `test_cli_check_exit_codes`: subprocess on a temp file, valid → 0, expired → 1
- [ ] **Step 2:** `python -m unittest discover -s .github/scripts -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement `scan_exceptions.py` to the interfaces above, stdlib only.
- [ ] **Step 4:** Rerun. Expected: all pass.
- [ ] **Step 5:** Create `scan_exceptions.md` with the policy text and an empty table.
- [ ] **Step 6: Commit.**

### Task 9: `security.yml` with pip-audit, govulncheck, npm audit and the exception check

**Files:** Create `.github/workflows/security.yml`. Modify `scan_exceptions.md` (day-one entries). Fix dependencies as needed.

**Interfaces (produces):** check names that Arlo will require (they must appear exactly like this in the GitHub UI):
- `Scan exceptions (expiry)`
- `pip-audit (backend)`
- `govulncheck (agent)`
- `npm audit (frontend, prod deps)`

Trivy (`Trivy (backend image)`) joins this workflow in Task 12.

- [ ] **Step 1: Workflow skeleton.**
  - Triggers: `pull_request` to main, `push` to main, `schedule: cron "23 6 * * 1"`, `workflow_dispatch`.
  - Top-level `permissions: contents: read`. No job reads a secret.
  - All `uses:` are SHA-pinned.
- [ ] **Step 2: Job `Scan exceptions (expiry)`.** Set up Python 3.11, then run `python -m unittest discover -s .github/scripts`, then `python .github/scripts/scan_exceptions.py check`.
- [ ] **Step 3: Job `pip-audit (backend)`.**
  - Set up Python 3.11 and `pip install pip-audit==<current>`.
  - Build the ignore args from `scan_exceptions.py ids pip-audit`, one `--ignore-vuln <ID>` each.
  - Run `pip-audit -r backend/requirements.txt --require-hashes --disable-pip --strict <ignore args>`.
  - Also audit `requirements-dev.txt` in the same job, because dev tools run in CI with repo access.
- [ ] **Step 4: Job `govulncheck (agent)`.** Set up Go the same way as `ci.yml` (`1.N`, `check-latest: true`), then `go install golang.org/x/vuln/cmd/govulncheck@<version>` (pinned, not `@latest`), then `govulncheck ./...` in `agent/`. govulncheck has no ignore list. A finding is fixed by a Go bump; if none exists yet, record an exception and make the step print and allow only that ID (parse `-format json`). Do this only if it actually happens.
- [ ] **Step 5: Job `npm audit (frontend, prod deps)`.** Set up Node 20, run `npm ci`, then `npm audit --omit=dev --audit-level=high` (blocking), then `npm audit` with `continue-on-error: true` (report only).
- [ ] **Step 6: Day-one triage.** Run the three audits locally (or push and read the PR run). For each finding:
  - upgrade (npm: bump, or use an `overrides` entry);
  - otherwise add an exception row, with expiry ≤90 days and the reason.

  Tally found / fixed / excepted per scanner.
- [ ] **Step 7: Canary red runs (Review Focus 3).**
  - Push a temporary commit pinning a known-vulnerable package in `requirements.in`, e.g. `python-multipart==0.0.6`, and recompile.
  - Confirm `pip-audit (backend)` goes red, then revert with a new commit.
  - Do the same for npm, locally only (preview deploys run on PRs), and paste the local output.
  - Do the same for govulncheck: temporarily set `go-version: "1.22"` and confirm stdlib findings fail it.
  - Record the run links.
- [ ] **Step 8: Gate and commit.** Run the full gate if any dependency moved.

### Task 10: Review and PR (B)

As Task 4 (`reviewer-risk`). The PR body includes the found / fixed / excepted tally, the canary red-run links, and the four check names.

## Stage C: CodeQL, Trivy, and the Semgrep trial (branch `feat/s2-c-codeql-trivy`)

### Task 11: `codeql.yml`

**Files:** Create `.github/workflows/codeql.yml`

- [ ] **Step 1: Workflow.**
  - Triggers: `pull_request` to main, `push` to main, and `schedule: cron "41 5 * * 1"`.
  - Top-level `permissions: contents: read`. The job gets `security-events: write`, `contents: read` and `actions: read`.
  - Matrix over `language` with these entries:

    | `language` | `build-mode` |
    | --- | --- |
    | `python` | `none` |
    | `javascript-typescript` | `none` |
    | `go` | `manual`, running `go build ./...` in `agent/` |
    | `actions` | `none` |

    The `actions` entry is Claude's addition: it is cheap and it scans the workflows themselves.
  - Use `github/codeql-action/init` and `analyze`, SHA-pinned, with the `default` query suite. Try `security-extended` once. Keep it only if the extra alerts are few enough to triage now, and record which suite you kept.
- [ ] **Step 2: Backlog.** Push and list the alerts with `gh api repos/firegiant9000/Senior-Cybersecurity-Project/code-scanning/alerts --paginate`. Fix the real ones in this PR. Dismiss false positives with a reason, and record each dismissal in `scan_exceptions.md` (scanner `codeql`). Tally found / fixed / dismissed.
- [ ] **Step 3:** Confirm that the PR shows the `CodeQL` code-scanning check. That is the name Arlo will require; it fails on new alerts only (spec).
- [ ] **Step 4: Commit.**

### Task 12: Trivy on the backend image

**Files:** Modify `.github/workflows/security.yml`, `backend/Dockerfile` (base digest), `scan_exceptions.md`.

- [ ] **Step 1: Pin the base by digest.** Pin both `FROM python:3.11-slim` references to `python:3.11-slim@sha256:<digest>`. Get the digest from `docker buildx imagetools inspect python:3.11-slim`, the multi-arch index digest. The docker ecosystem in `dependabot.yml` will keep it current.
- [ ] **Step 2: Job `Trivy (backend image)`.**
  - Build the default target from `backend` with `docker build -t ht-backend:ci backend`. Don't push it.
  - Generate `.trivyignore` from `scan_exceptions.py ids trivy`.
  - Blocking step: `aquasecurity/trivy-action`, SHA-pinned, with `image-ref: ht-backend:ci`, `severity: CRITICAL,HIGH`, `ignore-unfixed: true`, `exit-code: 1`, `trivyignores: .trivyignore`.
  - Second step, report only: all severities, `ignore-unfixed: false`, `exit-code: 0`, table format.

  Before pinning `trivy-action`, check its GitHub security advisories and recent release history. The action had a tag-compromise incident in 2026 (verify the details), so pin a SHA from a known-good release and say which one in the PR.
- [ ] **Step 3: Day-one triage.**
  - Fix OS findings by updating the base digest or adding `apt-get upgrade` in `base`, whichever the finding needs.
  - Fix Python findings by upgrading the package.
  - Otherwise add an exception.
  - Tally found / fixed / excepted.
- [ ] **Step 4: Canary red run.** Temporarily set the base to an old digest (e.g. a 2024 `python:3.11-slim`) and confirm the job goes red. Revert and record the link.
- [ ] **Step 5: Gate and commit.** Repeat Task 2 Step 6 (`/health`), because the base image changed.

### Task 13: Semgrep trial (throwaway)

**Files:** none committed, unless Semgrep is kept.

- [ ] **Step 1:** Run `semgrep scan --config p/python --config p/typescript --config p/golang --config p/secrets --metrics=off` locally, in a container, against the stage C tree. Save the output to the scratchpad.
- [ ] **Step 2:** Compare it with the CodeQL alerts from Task 11. List the Semgrep findings that are both unique (not found by CodeQL) and actionable (a real issue, not style).
- [ ] **Step 3: Decide.** If any unique, actionable finding exists, add a `Semgrep` job to `security.yml` with those rulesets, blocking, with exceptions under scanner `semgrep`. Otherwise add nothing. Either way, the PR body has a "Semgrep trial" section with the counts and the decision.

### Task 14: Review and PR (C)

As Task 4. The PR body includes both tallies, the Trivy canary link, the Semgrep section, the `trivy-action` SHA provenance note, and the check names `CodeQL` and `Trivy (backend image)`.

## Stage D: workflow hardening (branch `feat/s2-d-workflow-hardening`)

### Task 15: SHA pins, permissions, and secrets via env

**Files:** Modify `.github/workflows/ci.yml`, `secret-scan.yml`, `agent-release.yml`, `matcher-regression.yml` and `security.yml`.

- [ ] **Step 1: Pin every `uses:`.** For each one, resolve the full release tag, e.g. `actions/checkout@v4` → the latest `v4.x.y`, using `gh api repos/<o>/<r>/git/ref/tags/<tag>`. If the object type is `tag`, dereference it with `gh api repos/<o>/<r>/git/tags/<sha>`. Write `@<commit-sha> # v4.x.y`. Keep the current major versions; Dependabot proposes majors separately.
- [ ] **Step 2: Permissions.**
  - Add top-level `permissions: contents: read` to `ci.yml`, `matcher-regression.yml` and `secret-scan.yml`. `secret-scan.yml` keeps `pull-requests: read`.
  - In `agent-release.yml`, change the top level to `contents: read` and give the `build` job `contents: write`.
  - `deploy-preview` keeps its existing job block.
  - Check whether `deploy-frontend`'s Firebase action needs `checks: write` or `pull-requests: write` on push to main. Give it only what its docs require.
- [ ] **Step 3: Secrets out of `run:`.** Pass these through step `env:` and quote them as `"$VAR"` in the script:
  - `deploy-backend`: `RENDER_DEPLOY_HOOK_URL`;
  - `deploy-frontend` "Check Sentry source-map config": `SENTRY_AUTH_TOKEN`, `SENTRY_PROJECT`;
  - `post-deploy-healthcheck`: `BACKEND_URL`.

  Check: `git grep -n '\${{ secrets\.' .github/workflows` shows secrets only under `env:` or `with:`, never inside `run:` blocks.
- [ ] **Step 4: Add a regression check** to the `Scan exceptions (expiry)` job (renamed `Scan exceptions and workflow pins`; update the check-name list). It fails when any `uses:` other than a local `./` path is not followed by a 40-hex SHA: `! grep -rnP '^\s*(-\s*)?uses:\s*(?!\./)[^@\s]+@(?![0-9a-f]{40}\b)' .github/workflows`. Prove it with a temporary unpinned line (red run), then revert.
- [ ] **Step 5: Commit.**

### Task 16: `alembic check`

**Files:** `.github/workflows/ci.yml` (the drift step), possibly `backend/app/db/migrations/versions/<new>.py`, and `scan_exceptions.md`.

- [ ] **Step 1:** On a fresh Postgres, run `alembic -c app/db/alembic.ini upgrade head` and then `alembic … check`. List each drift item.
- [ ] **Step 2: Decide.** If every item can be fixed with a forward-only migration that changes no existing data (types, indexes, orphaned column drops on unused columns) in about 2 hours, write that migration, remove `continue-on-error`, rename the step to drop "(advisory)", and add a test or the CI step itself as the proof. If any item touches production data, stop and ask Arlo first. If the effort is larger, keep the step advisory and add an `alembic-check` exception row that lists the items, with an expiry of 90 days or less and the follow-up.
- [ ] **Step 3: Gate and commit.**

### Task 17: Review and PR (D)

As Task 4. The PR body includes the before/after count of pinned actions, the list of permissions widened per job and why, the pin-check red-run link, and the alembic decision.

## Stage E: close-out (no code PR unless docs change)

### Task 18: Required checks, roadmap and notes

- [ ] **Step 1:** Confirm that every gate has a green run on `main`: `gh run list --branch main --workflow security.yml` and `--workflow codeql.yml`.
- [ ] **Step 2:** Give Arlo the exact required-check list:
  - `Scan exceptions and workflow pins`
  - `pip-audit (backend)`
  - `govulncheck (agent)`
  - `npm audit (frontend, prod deps)`
  - `Trivy (backend image)`
  - `CodeQL`, plus `Semgrep` if kept
  - the existing `Backend Lint`, `Backend Tests`, `Frontend Lint`, `Frontend Tests` and `Agent (Go scanner)`

  Arlo applies them in branch protection or a ruleset.
- [ ] **Step 3: Small docs PR.**
  - Mark S2 DONE in the roadmap, with its PR numbers.
  - Fill `[N]` in the S2 résumé line from the A2 Step 1 audit count. Count distinct packages upgraded that had a published advisory.
  - Link `scan_exceptions.md`.
- [ ] **Step 4: Obsidian.** Update `Senior-Cybersecurity-Project/gotchas.md`, `decisions.md` and `todos.md` with durable, non-obvious facts, such as the Dependabot root cause, the `trivy-action` pin, and any exception that will need renewing. No secrets.
