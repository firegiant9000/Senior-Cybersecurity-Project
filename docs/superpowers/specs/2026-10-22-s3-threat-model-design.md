# S3: STRIDE threat model — design

Date: 2026-10-22. Owner: Arlo Kharod. Roadmap: `docs/PRODUCT_VIABILITY_ROADMAP.md`, milestone S3. Stacked on #223 (S1 close-out).

## Intent

S3 writes `docs/security/threat_model.md`: a STRIDE threat model of Hacker Tracker in which every threat is classified as exactly one of **CONTROL**, **TEST**, **ACCEPTED RISK** or **OPEN RISK**. It is the input to S4 (authorization assurance) and S5 (DAST and manual AppSec): every OPEN RISK names the milestone that closes it.

1. **Portfolio evidence.** The roadmap's résumé line ("Wrote a STRIDE threat model ... ([N] threats), mapping each to a control, a test or an accepted risk, and used it to drive the authorization suite") and its four interview questions are the bar: the upload path's spoofing and tampering threats; why a client-chosen `(scan_id, nonce)` is weaker than a timestamped signed request; the global-admin boundary; and "what threat did writing the model surface?".
2. **An honest work list for S4 and S5.** The model must say what is actually enforced and tested today, not what the README implies. Where they disagree, the model is right and the README is corrected.

## Goals

- `docs/security/threat_model.md` with the shape below, covering the scope below.
- Every threat row has exactly one classification, and its evidence is in the form required for that classification.
- A stdlib Python checker, `.github/scripts/check_threat_model.py`, with unittest tests, run in CI by the existing `Scan exceptions and workflow pins` job in `security.yml`. CI fails when the acceptance criteria break.
- Close-out:
  - the README `## Security design` links the model;
  - `docs/README.md:23` no longer says the threat model doesn't exist;
  - the roadmap marks S3 DONE in the S1/S2 style, with the résumé line's `[N]` filled in;
  - every OPEN RISK appears under the roadmap item that closes it.
- Obsidian:
  - `decisions.md`: an S3 section;
  - `todos.md`: the OPEN RISKs grouped by milestone, and the ACCEPTED RISKs with their review dates;
  - `gotchas.md`: anything new.

## Non-goals

- **Fixing anything.** Real vulnerabilities found become OPEN RISK rows with a milestone. No product code changes in S3.
- Implementing S4 or S5 work: the route-enumerating suite, real token verification in tests, security headers, the upload body limit, `/health`, ZAP.
- Changing repo settings, rulesets, secrets or branch protection (recorded as OPEN rows only).
- A formal methodology beyond STRIDE: no DREAD scores, no attack trees, no LINDDUN.
- Threats to the developer's workstation, GitHub's or Google's own infrastructure, or physical access. These go in one line under "Out of scope".

## Anti-goals (would be a failure even if CI is green)

- **Calling something TEST when the test runs under the autouse `verify_id_token` mock** (`backend/tests/conftest.py`) and the threat is about authentication or cross-tenant isolation. That test proves the handler logic, not the auth boundary.
- **A CONTROL row whose citation doesn't actually enforce the claim**: a path that exists but whose symbol doesn't implement the control, or a control that only applies to some routes and is cited as if it applied to all.
- **Publishing exploit detail for an unfixed vulnerability.** The repo is public. OPEN rows describe the weakness at the level needed to plan the fix: the class, the component and the missing control, never a step-by-step reproduction, a payload or a working request.
- **Padding the threat count** with near-duplicate rows to inflate `[N]` in the résumé line.
- **Contradictions left between the model and the README or the security docs.** If the README claims a control the code doesn't have, fix the README in this PR, or record it as a finding.

## Scope (Arlo, 2026-10-22)

One section per component:

1. **Agent enrollment**: enrollment tokens, the first-contact exchange, binding to an org.
2. **Agent upload**: `POST /inventory/scans`, schema validation, size, the 50,000-item cap.
3. **Agent token lifecycle**: issuance, rotation and grace, revocation, storage at rest.
4. **Replay**: the `(scan_id, nonce)` check and its window.
5. **Human authentication**: Firebase ID-token verification, revoked and disabled tokens, account linking (S0 `email_verified`), the email-link fallback.
6. **Org tenancy and the global-admin boundary**: per-handler scoping (`get_current_org`, `require_org_or_admin`, `check_org_access`, `require_same_org_membership`), org roles, global admins' cross-org access.
7. **Ingestion**: NVD, KEV and EPSS fetch, parse and store; the integrity and availability of the feeds.
8. **AI summary inputs**: the org data block, the grounding validator, the schema enforcement, the model's output reaching the UI. This builds on `docs/ai/case-study.md`'s "Threat model and blast radius" section rather than repeating it.
9. **Agent release supply chain** (added): tag moves, draft-release tampering, a compromised pinned tool in the job that holds `id-token: write`, consumers who skip verification.
10. **CI and deploy secrets** (added): the Firebase deploy key, the Render deploy hook, the scope of `GITHUB_TOKEN`, workflows triggered from forks.
11. **Platform-wide**: cross-cutting rows that would otherwise be repeated in every section: security headers, CORS, rate limiting (in-memory, per process), error disclosure, `/health`, logging of PII. *Builder's call where each row lives; prefer this section over repeating the same row.*

The known starting facts in the handoff (no security headers, per-process rate limits, no body limit on the upload, a static `/health`, the client-chosen nonce, S0's `email_verified`, S5a's data block) are **hypotheses to verify against the code**, not facts to copy.

## Document shape (Arlo, 2026-10-22)

1. **Header**: scope, the date, the commit the model was written against (the `origin/main` SHA the branch is based on once #223 merges; until then, `5fb462a` plus a note that #223 is pending, updated at the rebase), and how to read the tables. The owner of every ACCEPTED row is Arlo, including risks inherited from a third party such as GitHub or Google; the third party is named in the reason. *(My call.)*
2. **System overview**: one paragraph, plus a Mermaid data-flow diagram (it renders on GitHub) showing the actors (user browser, agent host, admin), the frontend (Firebase Hosting), the API (Render), Postgres, Firebase Auth, the NVD/KEV/EPSS feeds, the Gemini API and GitHub Actions/Releases. The trust boundaries are drawn as subgraphs.
3. **Trust boundaries**: a short numbered list (TB1, TB2, ...) that the rows can reference.
4. **Assets**: a short list of what is worth protecting (org inventory and findings, agent tokens, Firebase identities, the release artifacts, the deploy credentials, PII per `pii_inventory.md`).
5. **One section per component**, each with a single table:

   | ID | STRIDE | Threat | Class | Evidence | Notes |
   |----|--------|--------|-------|----------|-------|

   - **ID**: `T-<AREA>-NN`, stable, never renumbered. Removed threats are kept as rows with Notes `withdrawn: <reason>`. Area codes: `ENR`, `UPL`, `TOK`, `RPL`, `AUTH`, `TEN`, `ING`, `AI`, `REL`, `CI`, `PLAT`.
   - **STRIDE**: exactly one letter of `S T R I D E`. A threat that spans two categories becomes two rows only if the controls differ.
   - **Class**: exactly one of `CONTROL`, `TEST`, `ACCEPTED`, `OPEN`.
6. **Findings**: what writing the model surfaced that wasn't already known or documented. Each entry links to its row ID, so this section answers the interview question. Severity is described, but no exploit detail is given.
7. **OPEN RISK index**: the OPEN rows grouped by milestone, each linked to its roadmap item.
8. **ACCEPTED RISK register**: the ACCEPTED rows with the reason, the owner and the review date.
9. **Out of scope**: one paragraph.
10. **Maintenance**: when to update the model (a new route, a new external dependency, a new trust boundary), and that CI checks it.

## Evidence format (Arlo, 2026-10-22)

The Evidence cell must take the form required for the row's class. The checker parses these forms.

- **CONTROL**: one or more `` `path::symbol` (Lnn) `` entries, with paths relative to the repo root. The symbol is a function, class or method, or for YAML/JSON a key path (e.g. `.github/workflows/agent-release.yml::jobs.publish.permissions`). `Lnn` is the line at the time of writing; it's informational only and allowed to drift.
- **TEST**: one or more pytest node ids (`backend/tests/test_x.py::test_name` or `::TestClass::test_name`) or Go tests (`agent/internal/pkg/x_test.go::TestName`). The test must actually exercise the threat, and must not depend on the autouse auth mock if the threat is about authentication or tenancy (see Test honesty).
- **ACCEPTED**: `reason: ...; owner: Arlo; review: YYYY-MM-DD`. The default review date is **2027-04-22** (Arlo, 2026-10-22).
- **OPEN**: `milestone: S4|S5|S6|OWNER; item: <the roadmap item, quoted or paraphrased>`.

A row may combine evidence, for example a CONTROL that cites both the code and a unit test, but its class is the strongest *honest* one. TEST means a test that would fail if the control were removed.

## Test honesty (Arlo, 2026-10-22)

`backend/tests/conftest.py` autouse-mocks `firebase_admin.auth.verify_id_token`. For any authentication or tenancy threat:

- the row is **CONTROL**, citing the enforcing code path; existing tests may be mentioned in Notes;
- plus a separate **OPEN** row (or one shared OPEN row per component, at the builder's call) against S4's "real token verification" item.

Tests that don't depend on the mock, such as pure unit tests of a validator, the S5a injection corpus, or Go agent tests, can be TEST rows.

## Repo settings and owner actions (Arlo, 2026-10-22; milestone name is my call)

The repo settings still unapplied — the `agent-v*` tag ruleset, immutable releases, the S2 required checks and code-scanning rule on `main` — are **OPEN** rows with `milestone: OWNER`.

- The roadmap gets a new short item, **"Owner actions: repo hardening"**, listing them under S3's DONE note or near S4. *Placement is the builder's call.*
- The checker accepts `OWNER` as a milestone.
- Before writing these rows, check their current state with read-only `gh api` calls. Don't record a setting as missing if it has been applied.
  - If the token can't read a setting (some need admin scope), the row is still OPEN, with Notes saying `state unverified (Arlo to confirm)`, and it goes on the list of questions for Arlo before the PR. *(My call.)*

## Findings and severity (Arlo, 2026-10-22)

- Anything real becomes an OPEN row with a milestone and a Findings entry. Nothing is fixed in S3.
- **A severe finding** stops the work: it is raised with Arlo in chat before anything is written to a file, a commit, the PR or the vault. Severe here means exploitable cross-tenant access, an authentication bypass, or a leaked credential.
  - Arlo decides whether it's fixed first (outside S3), or written up at the planning level.
  - The threat rows are written by the controller in the main session, so there is always someone to stop. Evidence subagents report gaps back to the controller and never write them to files. If a subagent meets one of these mid-task, it stops and returns. *(My call.)*
- Contradictions between the code and the README or security docs are fixed in the docs in this PR (they are docs-only), and also listed in Findings.

## CI checker (Arlo, 2026-10-22)

`.github/scripts/check_threat_model.py`: stdlib only, Python 3.11, in the style of `scan_exceptions.py` and `check_sbom.py`. `test_check_threat_model.py` runs under the existing `python -m unittest discover -s .github/scripts` step. A new step in the same `Scan exceptions and workflow pins` job runs `python .github/scripts/check_threat_model.py docs/security/threat_model.md`.

What it parses:

- every Markdown table whose header row is exactly `ID | STRIDE | Threat | Class | Evidence | Notes`.

What it asserts, with a non-zero exit and one message per violation:

1. IDs match `^T-[A-Z]+-\d{2}$` and are unique across the document.
2. STRIDE is exactly one of `S T R I D E`.
3. Class is exactly one of `CONTROL TEST ACCEPTED OPEN`.
4. **CONTROL**: at least one `path::symbol`; every path exists in the repo; the symbol text appears in that file (a plain substring check, so it stays cheap).
5. **TEST**: at least one node id; the file exists, and it defines the test (Python `def test_name`, or Go `func TestName`). For `::Class::test`, both names appear.
6. **ACCEPTED**: `reason:`, `owner:` and `review: YYYY-MM-DD` are present, and the date parses. An expired review date fails the check, as `scan_exceptions.py` does for expiries (Arlo, 2026-10-22). This is intended to turn unrelated PRs red on the day a review comes due, and the Maintenance section says so.
7. **OPEN**: `milestone:` is one of `S4 S5 S6 OWNER`, and `item:` is non-empty.
8. **Mock guard**: a TEST row in an `AUTH` or `TEN` section fails unless its Notes contain `real-verification`. Until S4 lands, those rows are CONTROL plus OPEN. Only a test that uses real token verification earns that marker, and reviewers check that it's true. The checker can't prove what a control *does*; the semantic anti-goals are covered by the `reviewer-risk` pass and the controller's spot-check of citations. *(My call.)*
9. **Withdrawn** rows (Notes start with `withdrawn:`) skip checks 4–7.
9. At least one table was found, so a renamed header can't make the check pass vacuously.

The tests cover each rule's pass and fail cases on small inline fixtures, plus one test that runs the checker against the real `docs/security/threat_model.md`.

## Constraints

- **Docs plus one checker.** No changes to `backend/`, `frontend/` or `agent/` code.
- **The CI gate stays green**: `ci.yml`, `security.yml` and gitleaks.
- **Public repo**: no secrets, key IDs, connection strings, internal URLs (such as the Render deploy hook URL) or exploit steps.
- The frozen S5a eval files are untouched.
- The `security.yml` edit adds one step, with no new `uses:`, so the SHA-pin policy is unaffected.
- **PR**: a draft against `main`, with the stacked banner "Stacked on #223: review only the commits after `5fb462a`; merge after #223."

## Left to the builder

- The exact threat list per component, and the wording.
- Which trust boundaries to draw, and the diagram's layout.
- Whether an OPEN item is one row per gap or one shared row per component.
- Where the "Owner actions" item goes in the roadmap.
- The checker's internal structure and its messages.
