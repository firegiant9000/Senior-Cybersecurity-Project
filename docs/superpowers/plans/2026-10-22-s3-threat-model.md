# S3 STRIDE threat model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `docs/security/threat_model.md` (STRIDE, every row CONTROL/TEST/ACCEPTED/OPEN), a stdlib CI checker that enforces its acceptance criteria, and the S3 close-out docs, as a draft PR stacked on #223.

**Architecture:**
- A pure-function checker (`check_threat_model.py`) parses the model's tables and returns problem strings. It runs in the existing `scan-exceptions` job of `security.yml`.
- The model is written by the controller in the main session, from evidence gathered by parallel read-only `explorer` agents.
- The close-out edits are docs only.

**Tech Stack:** Python 3.11 stdlib (`re`, `pathlib`, `dataclasses`, `datetime`, `argparse`, `unittest`), Markdown with Mermaid, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-22-s3-threat-model-design.md` (approved by Arlo 2026-10-22). Executors read both.

## Global Constraints

- **Worktree** `C:/dev/ht-s3-a`, branch `docs/s3-threat-model`, base `5fb462a` (#223 HEAD). Never work from `C:/dev/Senior-Cybersecurity-Project`.
- **No changes** under `backend/`, `frontend/` or `agent/`. The frozen S5a eval files stay byte-identical.
- **Shell:** one shell command per Bash call: no `&&`, `;` or leading `cd`; use `git -C C:/dev/ht-s3-a`.
- **Commits:** `git -C C:/dev/ht-s3-a -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`.
  - The message file goes in the session scratchpad.
  - No Claude attribution anywhere.
- **Public repo:** no secrets, key IDs, connection strings, deploy-hook URLs or exploit steps. OPEN rows describe the class of weakness, the component and the missing control.
- **Severe finding** (exploitable cross-tenant access, an auth bypass, a leaked credential): stop and raise it with Arlo in chat before writing it anywhere. Subagents report gaps only to the controller.
- **Table header** is exactly `| ID | STRIDE | Threat | Class | Evidence | Notes |`.
- **IDs:** `T-<AREA>-NN`, where AREA ∈ `ENR UPL TOK RPL AUTH TEN ING AI REL CI PLAT`.
- **Classes:** `CONTROL TEST ACCEPTED OPEN`. **STRIDE:** one of `S T R I D E`.
- **Evidence forms:**
  - CONTROL: `` `path::symbol` (Lnn) ``
  - TEST: `` `path::test_name` `` or `` `path::Class::test_name` `` or `` `x_test.go::TestName` ``
  - ACCEPTED: `reason: …; owner: Arlo; review: YYYY-MM-DD` (default review date `2027-04-22`)
  - OPEN: `milestone: S4|S5|S6|OWNER; item: …`
- **Mock guard:** a TEST row with an `AUTH` or `TEN` ID needs `real-verification` in its Notes.
- **Withdrawn rows:** Notes start with `withdrawn:`, and the class/evidence checks are skipped.
- **ACCEPTED expiry:** expired when the review date is earlier than today (UTC), matching `scan_exceptions.py:143`. It fails CI (Arlo, 2026-10-22).
- **Ledger:** `C:/dev/Senior-Cybersecurity-Project/.superpowers/sdd/2026-10-22-s3-threat-model/progress.md`, append-only, gitignored.

## Review Focus

1. **A cell containing a literal `|`** (e.g. `a | b` in a threat description) shifts the columns. The checker should report a wrong cell count for that row, not crash or misread the class. Pinned in Task 1 (`test_wrong_cell_count_is_reported`).
2. **Evidence paths that escape the repo** (`../`, an absolute path, or a drive letter) must be rejected, not resolved. Pinned in Task 1 (`test_path_outside_repo_rejected`).
3. **A test name that is a prefix of another** (`test_foo` vs `test_foobar`) must not count as existing. Use a word-boundary match on `def`/`async def`/`func`. Pinned in Task 1 (`test_test_name_prefix_does_not_match`).
4. **A review date equal to today** is not expired; yesterday is. Pinned in Task 1 (`test_review_today_ok_yesterday_fails`).
5. **CRLF line endings and missing trailing pipes** (Windows checkout, `autocrlf`) must parse the same as LF. Pinned in Task 1 (`test_crlf_and_no_trailing_pipe_parse`).

---

### Task 1: Threat-model checker and its tests

**Files:**
- Create: `.github/scripts/check_threat_model.py`
- Create: `.github/scripts/test_check_threat_model.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Row: id: str; stride: str; threat: str; cls: str; evidence: str; notes: str; line: int`
  - `parse(text: str) -> tuple[list[Row], list[str]]`: the rows from every table whose header cells (stripped) are exactly `ID, STRIDE, Threat, Class, Evidence, Notes`, plus parse problems (wrong cell count, with the line number). The separator row is skipped. Leading/trailing pipes are optional, and `\r` is stripped.
  - `check(text: str, repo_root: Path, today: date) -> list[str]`: all problems, each prefixed with the row id (or `line N`). Empty means the document is valid.
  - `main(argv: list[str] | None = None) -> int`: CLI `check_threat_model.py <doc.md> [--repo-root PATH]`. `--repo-root` defaults to `Path(__file__).resolve().parents[2]`, and today is `datetime.now(timezone.utc).date()`. Prints one `::error::<problem>` line per problem and returns 1, or prints `threat model OK: <N> threats (<counts per class>)` and returns 0.

Rules (from the spec's "CI checker" section; implement exactly):
1. ID matches `^T-(ENR|UPL|TOK|RPL|AUTH|TEN|ING|AI|REL|CI|PLAT)-\d{2}$` and is unique.
2. STRIDE ∈ {S,T,R,I,D,E}.
3. Class ∈ {CONTROL,TEST,ACCEPTED,OPEN}.
4. CONTROL: the evidence contains ≥1 `` `path::symbol` `` (regex ``` `([^`:\s]+)::([^`]+)` ```).
   - The path must be relative, with no `..` segment and no drive letter, and must exist under `repo_root`.
   - Every `.`-separated segment of the symbol must appear as a substring of the file text. That covers `Class.method` and YAML key paths like `jobs.publish.permissions`.
5. TEST: ≥1 backticked node id, with the same path rules.
   - The final `::` segment must be defined: Python `^\s*(async\s+)?def\s+NAME\s*\(`, Go `^func\s+NAME\s*\(`, both multiline.
   - A middle `::Class` segment must match `^\s*class\s+Class\b`.
   - Mock guard: an ID area of `AUTH` or `TEN` requires `real-verification` in Notes.
6. ACCEPTED: `reason:\s*\S`, `owner:\s*\S` and `review:\s*(\d{4}-\d{2}-\d{2})` are all present. The date must parse with `date.fromisoformat`, and `review < today` is an error, `"<id>: review date <d> has passed (today <t>)"`.
7. OPEN: `milestone:\s*(S4|S5|S6|OWNER)\b` and `item:\s*\S` are present.
8. Notes starting with `withdrawn:` skip rules 4–7. Rules 1–3 still apply.
9. Zero rows parsed is an error: `"no threat tables found (header must be: ID | STRIDE | Threat | Class | Evidence | Notes)"`.

- [ ] **Step 1: Write the failing tests** in `test_check_threat_model.py`, styled like `test_check_sbom.py` (`import check_threat_model as ctm`). Use a `tempfile.TemporaryDirectory` repo root holding:
  - `src/app.py`, containing `class Guard:\n    def enforce(self): pass\n`;
  - `tests/test_app.py`, containing `class TestGuard:\n    def test_enforced(self): pass\n\ndef test_foobar(): pass\n`;
  - `agent/x_test.go`, containing `func TestScan(t *testing.T) {}`.

  `TODAY = date(2026, 10, 22)`. Each test builds a one-row table with a helper `doc(*rows)` and asserts on `ctm.check(...)`. Tests and their assertions:
  - `test_valid_rows_pass`: one valid row per class gives `[]`. CONTROL is `` `src/app.py::Guard.enforce` (L2) ``. TEST is `` `tests/test_app.py::TestGuard::test_enforced` ``. ACCEPTED is `reason: r; owner: Arlo; review: 2027-04-22`. OPEN is `milestone: S4; item: route suite`.
  - `test_bad_id_and_duplicate_id`: `T-XYZ-01` and a repeated `T-UPL-01` give 2 problems naming each.
  - `test_bad_stride_and_class`: `X` and `MAYBE` each give one problem.
  - `test_control_missing_path_or_symbol`: `src/nope.py::f` and `src/app.py::Guard.missing` each give one problem.
  - `test_path_outside_repo_rejected`: `../etc/passwd::x`, `/etc/passwd::x` and `C:/x.py::y` each give a problem containing `outside repo`.
  - `test_test_name_prefix_does_not_match`: `tests/test_app.py::test_foo` gives one problem, and `::test_foobar` passes.
  - `test_go_test_found`: `agent/x_test.go::TestScan` passes.
  - `test_mock_guard`: a TEST row `T-TEN-01` without `real-verification` gives a problem containing `real-verification`. With it, the row passes.
  - `test_review_today_ok_yesterday_fails`: `review: 2026-10-22` passes, and `2026-10-21` gives a problem containing `has passed`.
  - `test_accepted_missing_fields`: no `owner:` gives a problem.
  - `test_open_bad_milestone`: `milestone: S9` gives a problem.
  - `test_withdrawn_skips_evidence`: CONTROL with empty evidence and Notes `withdrawn: dup of T-UPL-02` gives `[]`.
  - `test_wrong_cell_count_is_reported`: a row with 7 cells gives a problem containing `cells`, and no exception.
  - `test_crlf_and_no_trailing_pipe_parse`: the valid doc with `\r\n`, without the trailing pipes, gives `[]`.
  - `test_no_tables_is_error`: `"# empty\n"` gives one problem containing `no threat tables`.
  - `test_main_exit_codes`: write the docs to the temp dir. `main([path, "--repo-root", tmp])` returns 0 for valid and 1 for invalid. Capture stdout with `redirect_stdout`, and for invalid it contains `::error::`.
  - `test_real_threat_model`: `@unittest.skipUnless(REAL.exists(), ...)`, where `REAL = Path(__file__).resolve().parents[2] / "docs/security/threat_model.md"`. It asserts that `check(REAL.read_text(encoding="utf-8"), parents[2], today_utc) == []`.

- [ ] **Step 2: Run them and check that they fail.** Run `python -m unittest discover -s C:/dev/ht-s3-a/.github/scripts -p "test_check_threat_model.py"`. Expect an ImportError / ModuleNotFoundError for `check_threat_model`.

- [ ] **Step 3: Implement `check_threat_model.py`.**
  - Use the module docstring and the `::error::` output style of `check_sbom.py`.
  - Use the `@dataclass` + `validate`-style structure of `scan_exceptions.py`.
  - No third-party imports.

- [ ] **Step 4: Run all script tests and check that they pass.** Run `python -m unittest discover -s C:/dev/ht-s3-a/.github/scripts`. Expect `OK`: the existing `check_sbom`/`scan_exceptions` tests plus the new ones, with `test_real_threat_model` skipped.

- [ ] **Step 5: Commit** both files: `ci(security): add threat model checker (S3)`.

### Task 2: Evidence gathering (controller-run, no commit)

The controller dispatches **5 parallel `explorer` agents** (Sonnet), read-only, against `C:/dev/ht-s3-a`. Each returns three things:
- **(a) Controls:** `path::symbol (Lnn)`, plus one line on what it enforces and on which routes.
- **(b) Existing tests:** the exact node id, and whether it runs under the autouse `verify_id_token` mock in `backend/tests/conftest.py`.
- **(c) Gaps:** stated as "missing control X on Y", with **no exploit steps**. If a gap looks like exploitable cross-tenant access, an auth bypass or a leaked credential, the agent marks it `SEVERE?` and stops elaborating.

Every agent verifies the hypotheses listed for it, and does not assume them.

| Agent | Scope (spec sections) | Hypotheses to verify |
|---|---|---|
| E1 | Agent enrollment, upload, token lifecycle, replay (1–4); `docs/security/agent_enrollment.md` | No body-size limit on `POST /inventory/scans`; replay is a client-chosen `(scan_id, nonce)`, with the window and storage noted; how tokens are stored (hashed?); the rotation grace; revocation |
| E2 | Human auth and tenancy (5–6) | `verify_id_token` with `check_revoked`; S0 `email_verified` linking; the email-link fallback; `get_current_org`, `require_org_or_admin`, `check_org_access`, `require_same_org_membership`; global-admin bypass points; list every org-scoped route **not** using one of these |
| E3 | Ingestion and AI summary (7–8); `docs/ai/case-study.md` | Feed fetch: TLS, timeouts, size limits, parse failure handling, who can trigger a sync; AI: the data block, the grounding validator, the schema, how the output is rendered in the frontend (escaped?) |
| E4 | Release supply chain and CI/deploy secrets (9–10); `docs/security/agent_release_verification.md`, `.github/workflows/*` | Job-level `id-token`/`contents` permissions; `pull_request_target` usage; where the Firebase deploy key and Render hook are used and on which triggers; and read-only `gh api` checks of repo rulesets, tag protection, immutable releases and required checks on `main` (report "unreadable" if 403/404) |
| E5 | Platform-wide (11); `docs/security/pii_inventory.md`, `privacy.md` | No security headers (app and `firebase.json`); CORS config; slowapi limits, which routes, the per-process store; error handlers (stack traces?); a static `/health`; PII in logs; the README claim "Uploaded inventory files are size-limited" vs the agent upload path |

- [ ] **Step 1:** Dispatch E1–E5 in one message.
- [ ] **Step 2:** On return, triage any `SEVERE?` item. If one is confirmed, **stop and raise it with Arlo** before Task 3.
- [ ] **Step 3:** Append a summary of the gathering and the counts to the ledger.

### Task 3: Write `docs/security/threat_model.md` (controller)

**Files:**
- Create: `docs/security/threat_model.md`

**Interfaces:**
- Consumes: the Task 1 checker, and the Task 2 reports.
- Produces: the stable row IDs that Task 4 cites in the roadmap, and the row total `N` for the résumé line.

- [ ] **Step 1: Write the document** with the 10 sections in the spec's "Document shape" order.
  - **Header:** "Written against `5fb462a` (#223 pending)".
  - **Mermaid `flowchart LR`** with `subgraph` trust boundaries.
  - **11 component tables.**
  - **Findings:** each finding links to its row ID.
  - **OPEN index by milestone.**
  - **ACCEPTED register.**
  - **Out of scope.**
  - **Maintenance:** says CI checks the model, and that an expired review date turns every PR red until the review is done.
  - **Applying the rules:** test honesty, so auth/tenancy is CONTROL plus OPEN against S4 "real token verification". No padding, no exploit detail.
- [ ] **Step 2: Run the checker on it.** Run `python C:/dev/ht-s3-a/.github/scripts/check_threat_model.py C:/dev/ht-s3-a/docs/security/threat_model.md`. Expect `threat model OK: N threats (...)`.
- [ ] **Step 3: Rerun all the script tests.** Run `python -m unittest discover -s C:/dev/ht-s3-a/.github/scripts`. Expect `OK`, with `test_real_threat_model` now **not** skipped.
- [ ] **Step 4: Spot-check citations.**
  - The controller opens at least 10 random CONTROL/TEST citations and confirms that each one enforces or tests what its row claims.
  - Fix any that are wrong, and record the sample in the ledger.
- [ ] **Step 5: Commit** `docs(security): add STRIDE threat model (S3)`.

### Task 4: CI wiring and close-out docs

**Files:**
- Modify: `.github/workflows/security.yml`
  - After the `Check exception list (format and expiry)` step (line ~33), add a step named `Check threat model (classifications and evidence)` that runs `python .github/scripts/check_threat_model.py docs/security/threat_model.md`. No new `uses:`.
  - Rename the step at line 29 to `Test the security scripts`.
- Modify: `README.md` `## Security design` (line ~159).
  - Add a **Threat model** bullet first, linking `docs/security/threat_model.md`, with a one-line summary (N threats, and the counts per class).
  - Correct any README claim that Task 2 contradicted, e.g. the upload size limit wording (line ~183) if the agent path has no limit.
- Modify: `docs/README.md:23`. Replace the "doesn't exist yet" wording with a link to the model.
- Modify: `docs/PRODUCT_VIABILITY_ROADMAP.md`:
  - `#### S3`: retitle it `#### S3. STRIDE threat model — DONE 2026-10-2X (PR #NNN)` in the S1/S2 style, with a short outcome note, and fill in `[N]` in the résumé line.
  - `#### S4` and `#### S5`: add every OPEN row's ID to its item. Append "(T-… )" references, or add a bullet where the item is missing.
  - Add a new short `#### Owner actions: repo hardening` item, listing the OWNER rows' IDs. Put it after S3.
  - Record the list of added items for Arlo.

- [ ] **Step 1:** Make the edits above.
- [ ] **Step 2: Run the checker as CI will.** Run `python C:/dev/ht-s3-a/.github/scripts/check_threat_model.py C:/dev/ht-s3-a/docs/security/threat_model.md`. Expect OK.
- [ ] **Step 3: Check that every OPEN ID appears in the roadmap.** For each OPEN ID, grep the roadmap (Grep tool, the pattern being the ID). Expect a match for all of them.
- [ ] **Step 4: Commit** `docs: close out S3 (README, roadmap, CI step)`. The PR number in the S3 heading is filled in after Task 6 opens the PR, and amended in a follow-up commit.

### Task 5: Review

- [ ] **Step 1:** Dispatch one `reviewer-risk` (Sonnet) over `git diff 5fb462a..HEAD`, the spec and the plan. It focuses on:
  - honest classification (no TEST under the mock; CONTROL citations that really enforce);
  - exploit detail in a public doc;
  - the checker's correctness;
  - the README claims vs the code.
- [ ] **Step 2:** Fix the confirmed findings (`superpowers:receiving-code-review`), and commit `docs(security): address S3 review`.
- [ ] **Step 3:** Re-review the fix diff only: Haiku if it's small, Sonnet otherwise.
  - At most 2 fix rounds. Still failing after that, stop and bring it to Arlo.

### Task 6: Push, draft PR, Obsidian, ledger

- [ ] **Step 1:** `gh auth status`, and confirm that `firegiant9000` is the active account.
- [ ] **Step 2:** `git -C C:/dev/ht-s3-a push origin docs/s3-threat-model:refs/heads/docs/s3-threat-model`.
- [ ] **Step 3: Open the draft PR.**
  - Run `gh pr create --draft --base main --head docs/s3-threat-model --title "docs(security): S3 STRIDE threat model" --body-file <scratchpad>`.
  - The body starts with the banner "Stacked on #223: review only the commits after `5fb462a`; merge after #223." Then it gives the summary, the counts per class, the Findings at the planning level, and the OPEN items added to the roadmap.
  - Confirm `gh pr view --json baseRefName` returns `main`.
- [ ] **Step 4:** Put the PR number into the roadmap S3 heading, commit `docs: link S3 PR`, and push.
- [ ] **Step 5:** Run `gh pr checks <n>`, once more if it flakes. Expect `Scan exceptions and workflow pins` to be green and to include the new step.
- [ ] **Step 6: Obsidian** (vault `claude`, folder `Senior-Cybersecurity-Project/`). No secrets, identifiers or exploit detail.
  - `decisions.md`: add an S3 section with the spec rulings and my calls.
  - `todos.md`: add the OPEN rows by milestone, plus the ACCEPTED review dates.
  - `gotchas.md`: add anything new.
- [ ] **Step 7:** Give Arlo the "Rulings I made" list. Then delete the plan workspace (`.superpowers/sdd/2026-10-22-s3-threat-model/`).
  - The spec and plan stay committed.
  - Remind Arlo of the post-#223 rebase: `git rebase --onto origin/main 5fb462a docs/s3-threat-model`, then `--force-with-lease`. This needs Arlo's OK.
