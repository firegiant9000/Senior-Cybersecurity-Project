# S1 Agent Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `.github/workflows/agent-release.yml` so `agent-v*` tags publish a verified, attested release (binaries, per-binary CycloneDX SBOMs, `SHA256SUMS`, provenance and SBOM attestations), prove it with dispatch dry runs and a draft-release rehearsal, then ship `agent-v0.1.0`.

**Architecture:** There are four jobs, with least privilege split by job:

- `build` holds the OIDC token and attests;
- `publish` creates a **draft** release;
- `verify` downloads what a consumer would get, checks it, and undrafts only on a tag run;
- `cleanup-rehearsal` deletes rehearsal drafts.

The SBOM's correctness is checked by a small, unit-tested Python script that runs in the existing `security.yml` unittest step.

**Tech Stack:** GitHub Actions, Go 1.27, `actions/attest@v4`, `cyclonedx-gomod`, `govulncheck`, `gh` CLI, Python 3 stdlib (unittest).

**Spec:** `docs/superpowers/specs/2026-10-21-s1-agent-release-design.md` (approved by Arlo 2026-10-22). Executors read both.

## Global Constraints

- **Action pins.** Every `uses:` is `owner/repo@<40-hex> # vX.Y.Z`. Pins resolved with `gh api repos/<o>/<r>/commits/<tag> --jq .sha` on 2026-10-22:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `actions/setup-go@b7ad1dad31e06c5925ef5d2fc7ad053ef454303e # v7.0.0`
  - `actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2`
  - `actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2`
  - `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2` (used directly; `attest-build-provenance` and `attest-sbom` are now wrappers over it)
- **Tool pins:** `go install golang.org/x/vuln/cmd/govulncheck@v1.9.0` (same as `security.yml`) and `go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@v1.12.0`.
- **Runner:** `runs-on: ubuntu-24.04` on every job in this workflow.
- **Permissions:** top-level `permissions: contents: read`. No job holds both `id-token: write` and `contents: write`. `build` has `contents: read`, `id-token: write`, `attestations: write`. No `artifact-metadata`: it's only needed for registry storage records.
- **Checkouts:** every checkout sets `persist-credentials: false`.
- **No secrets:** the workflow reads none. Remove every `AGENT_SIGNING_GPG_*` reference.
- **`ScannerVersion` stays `"0.1.0"`** in `agent/internal/output/json.go`.
- **Artifact names:**
  - `hacker-tracker-${VERSION}-linux-{amd64,arm64}`;
  - SBOMs are `<binary>.cdx.json`;
  - `SHA256SUMS` covers all four files.
  - `VERSION` is `0.0.0-dev` on dispatches.
- **Build ldflags unchanged:** `-s -w -X github.com/firegiant9000/hacker-tracker/agent/internal/output.ScannerVersion=${VERSION}`, plus `CGO_ENABLED=0 -trimpath`.
- **Build output path:** `$RUNNER_TEMP/dist`, outside the git working tree.
- **Rehearsal release name (plan ruling):** `rehearsal-agent-${{ github.run_id }}`, not the spec's `agent-v0.0.0-rehearsal-…`. The name stays outside the `agent-v*` trigger glob and the "real release" namespace; nothing else changes.
- **Repo slug in verify flags:** `firegiant9000/Senior-Cybersecurity-Project`. Signer workflow: `firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml`.
- **Commits:** `git -C <worktree> -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`. No Claude attribution.
- **Shell:** one command per Bash call; Go and Python run in the `golang:1.27` and `python:3.11-slim` containers (no bare `go` on the host); `MSYS_NO_PATHCONV=1` for `docker run -v C:/...`.
- **Hard stops:** no `gh workflow run`, tag push, release creation or deletion, settings change, or `gh pr ready` by Claude. Arlo does these, or gives an explicit go-ahead at that moment.

## Review Focus

1. **A tampered asset must fail verification.** In every mode, `verify` copies one binary, appends a byte, and asserts `gh attestation verify` **fails** on the copy, which proves the check isn't vacuous (Task 2, Step 2).
2. **A rehearsal must never leave a draft or a tag behind,** even when `publish` or `verify` fails. `cleanup-rehearsal` runs with `if: always()` and asserts afterwards that no tag `rehearsal-agent-<run_id>` exists (Task 2, Step 3).
3. **An old runner `gh` that lacks a flag must fail loudly, not skip the check.** `verify` feature-detects `--signer-workflow`, `--source-ref` and `--predicate-type` in `gh attestation verify --help` and exits 1 if any is missing (Task 2, Step 2).
4. **An SBOM that doesn't describe the shipped binary must block.** That means a main component at `(devel)` or with the wrong version, a missing stdlib component, or a non-CycloneDX file. `check_sbom.py` exits non-zero (Task 1, Steps 1–4).
5. **A tag whose `ScannerVersion` doesn't match, or a re-run on a tag whose release already exists, must stop before anything is published.** The existing tag check stays first in `build`, and `gh release create` fails on an existing release, which the PR body's failure-handling note covers (Task 1, Step 6).

---

## Stage A: workflow, docs and proof (one draft PR to `main`)

Worktree `C:\dev\ht-s1-a`, branch `feat/s1-a-agent-release`. Created from `origin/main` `9ad0d18` with upstream unset; the spec was committed at `95e444e`.

### Task 1: The SBOM checker and the `build` job

**Files:**
- Create: `.github/scripts/check_sbom.py`
- Create: `.github/scripts/test_check_sbom.py`
- Modify: `.github/workflows/agent-release.yml` (the whole `build` job; header comment; triggers)

**Interfaces:**
- Produces:
  - `check_sbom.py <sbom.json> --version <vX.Y.Z> --go-version <goX.Y.Z>` exits 0 when valid, and exits 1 with one `::error::` line per problem otherwise;
  - `def check(sbom: dict, version: str, go_version: str) -> list[str]` returns a list of problem strings, empty when valid;
  - build-job output `version` (e.g. `0.1.0` or `0.0.0-dev`);
  - run artifact `agent-linux-${version}` containing the 2 binaries, 2 SBOMs and `SHA256SUMS`.

- [ ] **Step 1: Generate a real SBOM fixture locally.**
  - In `golang:1.27` (mount the worktree), build `hacker-tracker-0.0.0-dev-linux-amd64` with the Global Constraints ldflags into `/tmp/dist`.
  - Install `cyclonedx-gomod@v1.12.0`, then run `cyclonedx-gomod bin -h` and record the real flag names for JSON output, the output file, the version override and stdlib inclusion. Use those names everywhere below.
  - Generate the SBOM with the version set to `v0.0.0-dev` and stdlib included.
  - Save a trimmed copy (metadata, plus the main and stdlib components) as `.github/scripts/testdata/sbom_valid.cdx.json`.
  - Expected: `metadata.component.version == "v0.0.0-dev"`, and a component for the Go stdlib whose version is `go1.27.x`.
  - Record exactly which fields carry these values; the checker reads those fields.
  - If the version flag can't override `(devel)`, stop and report: the spec needs a different approach.

- [ ] **Step 2: Write the failing tests in `test_check_sbom.py`** (unittest, matching `test_scan_exceptions.py` style; load the fixture from `testdata/`):
  - `test_valid_sbom_passes`: `check(fixture, "v0.0.0-dev", "<go version from fixture>") == []`.
  - `test_wrong_main_version_fails`: `check(fixture, "v0.1.0", go)` names the main component version.
  - `test_devel_main_version_fails`: set the main component version to `(devel)`; the result is non-empty.
  - `test_missing_stdlib_fails`: remove the stdlib component; the result names the stdlib.
  - `test_wrong_go_version_fails`: `check(fixture, v, "go1.20.0")` is non-empty.
  - `test_not_cyclonedx_fails`: `bomFormat` set to `"SPDX"`; the result is non-empty.
  - `test_cli_exit_codes`: run `main([...])` against the fixture: 0 when valid, 1 when the version is wrong.

- [ ] **Step 3: Run the tests and see them fail.**
  Run: `MSYS_NO_PATHCONV=1 docker run --rm -v C:/dev/ht-s1-a:/src -w /src python:3.11-slim python -m unittest discover -s .github/scripts`
  Expected: the `check_sbom` import fails; `test_scan_exceptions` is still OK.

- [ ] **Step 4: Implement `check_sbom.py`** (stdlib only: `argparse`, `json`, `sys`). Use the field locations recorded in Step 1. Re-run the Step 3 command; expected all OK (including the 17 existing scan_exceptions tests).

- [ ] **Step 5: Commit** the script, the tests and the fixture: `feat(ci): SBOM checker for agent release artifacts`.

- [ ] **Step 6: Rewrite the header, triggers and `build` job of `agent-release.yml`.**
  - Header comment: what the workflow does now (attested, SBOM, draft → verify → publish), and a link to `docs/security/agent_release_verification.md`. No GPG text.
  - Triggers: `push.tags: ["agent-v*"]`, plus `workflow_dispatch.inputs.rehearse` (`type: boolean`, `default: false`, with a description saying it creates and deletes a draft release and pushes no tag). **Remove the `ref` input.**
  - Checkout `with: persist-credentials: false` only, so it checks out `github.sha`.
  - Setup-go: `go-version: "1.27"`, `check-latest: true`, `cache: false`.
  - Keep "Resolve version" (now also an output of the job, `outputs.version`) and the `ScannerVersion` tag check, unchanged in logic.
  - Keep "Vet & test".
  - Build into `$RUNNER_TEMP/dist`.
  - Install both tools, at the pins in Global Constraints.
  - **govulncheck:** `govulncheck -mode binary "$f"` for each binary, blocking.
  - **SBOM:** one `cyclonedx-gomod bin` per binary, writing `$RUNNER_TEMP/dist/<binary>.cdx.json` with the version set to `v${VERSION}`. Then `python3 .github/scripts/check_sbom.py <sbom> --version v${VERSION} --go-version "$(go env GOVERSION)"` for each SBOM.
  - **Checksums:** `sha256sum` over the 4 files, written to `SHA256SUMS` (run from inside `dist` so the names are bare).
  - **Attest provenance:** `actions/attest` with `subject-path` set to the two binaries (newline list).
  - **Attest SBOMs:** `actions/attest` twice, once per binary, each with `subject-path: <binary>` and `sbom-path: <binary>.cdx.json`.
  - **Upload:** `upload-artifact` named `agent-linux-${{ steps.version.outputs.version }}`, path `${{ runner.temp }}/dist/*`, `if-no-files-found: error`.
  - Job permissions as in Global Constraints. No publish step in this job.
  - Keep the macOS stub comment at the bottom, repointed to the new doc.

- [ ] **Step 7: Run the local gate for the `build` job.**
  - **actionlint:** `docker run --rm -v C:/dev/ht-s1-a:/repo -w /repo rhysd/actionlint:latest -color` (with `MSYS_NO_PATHCONV=1`). Expected: no findings. If the pull flakes, YAML-parse with `python -c "import yaml…"` in `python:3.11-slim` after `pip install pyyaml`, and note the fallback in the report.
  - **Pin grep:** copy both greps from `security.yml` (the "Check every action is pinned" step) and run them against `.github/workflows`. Expected: no matches.
  - **Agent checks:** in `golang:1.27`, `go vet ./...`, `gofmt -l .` (empty) and `go test ./...` in `agent/`, all clean.
  - **Tool checks:** in `golang:1.27`, `govulncheck -mode binary` on the Step 1 binary (expected: no vulnerabilities, or report them; don't suppress), then `check_sbom.py` on the Step 1 SBOM (expected: exit 0).

- [ ] **Step 8: Commit:** `feat(ci): attested agent build with binary govulncheck and CycloneDX SBOMs`.

### Task 2: The `publish`, `verify` and `cleanup-rehearsal` jobs

**Files:**
- Modify: `.github/workflows/agent-release.yml` (append three jobs)

**Interfaces:**
- Consumes: `needs.build.outputs.version` and the run artifact `agent-linux-<version>` from Task 1.
- Produces: the release-body file layout and the draft/undraft behaviour that Task 3's doc describes. The verify command lines are reused verbatim in the doc.

- [ ] **Step 1: Add the `publish` job.**
  - `if: startsWith(github.ref, 'refs/tags/agent-v') || inputs.rehearse`; `needs: build`; `permissions: contents: write`.
  - Download the artifact to `dist/`.
  - Write the release body to `body.md` with a heredoc. The body states:
    - the version;
    - the Go version, taken from the SBOM's stdlib component (or emitted as a build output; your choice);
    - the artifact list;
    - verification in two lines: `gh release download`, then `gh attestation verify <binary> --repo firegiant9000/Senior-Cybersecurity-Project`;
    - an **absolute** link `https://github.com/firegiant9000/Senior-Cybersecurity-Project/blob/main/docs/security/agent_release_verification.md`.
  - **Tag runs:** `gh release create "$GITHUB_REF_NAME" dist/* --repo "$GITHUB_REPOSITORY" --draft --verify-tag --title "Hacker Tracker agent v${VERSION}" --notes-file body.md`.
  - **Rehearsal runs:** the same command, but with the name `rehearsal-agent-${GITHUB_RUN_ID}`, `--target "$GITHUB_SHA"` and no `--verify-tag`.
  - `GH_TOKEN: ${{ github.token }}` via `env:`.
  - Use no `${{ }}` inside `run:` except through `env:` (injection hygiene).

- [ ] **Step 2: Add the `verify` job.**
  - **Runs:** `needs: [build, publish]` with `if: always() && needs.build.result == 'success' && (needs.publish.result == 'success' || needs.publish.result == 'skipped')`.
  - **Permissions:** `contents: write`, which reading the draft and undrafting both need. No `id-token`.
  - **Feature-detect the `gh` flags:** print `gh --version`, then for each of `--signer-workflow`, `--source-ref` and `--predicate-type`, `gh attestation verify --help | grep -q -- "$flag" || { echo "::error::gh lacks $flag"; exit 1; }`. If `--source-digest` is present, use it too (with `$GITHUB_SHA`).
  - **Get the files:**
    - tag and rehearsal runs: `gh release download <name> --repo "$GITHUB_REPOSITORY" --dir dl`. If that can't find the draft, resolve the release ID with `gh api repos/$GITHUB_REPOSITORY/releases --jq '.[] | select(.tag_name=="<name>") | .id'` and download each asset with `gh api -H "Accept: application/octet-stream" repos/$GITHUB_REPOSITORY/releases/assets/<id>`. Record which path worked.
    - plain dispatches: `download-artifact` into `dl/`.
  - **Assert the file set:** exactly 2 binaries, 2 `.cdx.json` and `SHA256SUMS`.
  - **Checksums:** `sha256sum -c SHA256SUMS` in `dl/`.
  - **Verify each binary:**
    - `gh attestation verify "$b" --repo firegiant9000/Senior-Cybersecurity-Project --signer-workflow firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml --source-ref "$GITHUB_REF" --deny-self-hosted-runners`;
    - the same with `--predicate-type https://cyclonedx.org/bom`.
    - `--source-ref` is passed in **every** mode, so dry runs also prove the flag (plan ruling: this strengthens the spec, which limited it to tags).
  - **Tamper self-test (Review Focus 1):** `cp` the amd64 binary to `tampered`, `printf 'x' >> tampered`, then `if gh attestation verify tampered <same flags>; then echo "::error::tampered binary verified"; exit 1; fi`.
  - **Undraft, last step:** `if: startsWith(github.ref, 'refs/tags/agent-v')`, run `gh release edit "$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" --draft=false --latest`.

- [ ] **Step 3: Add the `cleanup-rehearsal` job (Review Focus 2).**
  - **Runs:** `needs: [publish, verify]` with `if: always() && inputs.rehearse`; `permissions: contents: write`.
  - **Delete:** `gh release delete "rehearsal-agent-${GITHUB_RUN_ID}" --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag`. Tolerate "release not found" only; fail on anything else.
  - **Assert no tag left behind:** `gh api repos/$GITHUB_REPOSITORY/git/matching-refs/tags/rehearsal-agent-${GITHUB_RUN_ID} --jq length` must print `0`.

- [ ] **Step 4: Run the local gate for the whole workflow.**
  - Re-run actionlint (or the fallback) and the pin grep from Task 1 Step 7.
  - Grep the workflow for `secrets.` and `GPG`. Expected: no matches.
  - Grep for `contents: write` and `id-token: write`: they must never appear in the same job block.

- [ ] **Step 5: Commit:** `feat(ci): draft release, consumer-style verify with tamper self-test, rehearsal cleanup`.

### Task 3: Consumer documentation and link fixes

**Files:**
- Create: `docs/security/agent_release_verification.md`
- Modify (replace with a stub): `docs/security/agent_release_signing.md`
- Modify:
  - `agent/README.md:67-72`;
  - `docs/security/agent_enrollment.md:43`;
  - `docs/README.md:21`;
  - `README.md:126-133`;
  - `docs/agent_auto_update.md:3` (append one sentence to the status note).

**Interfaces:**
- Consumes: the exact verify commands and flags from Task 2, Step 2, and the release name and asset names from Global Constraints.

- [ ] **Step 1: Write `agent_release_verification.md`** with these sections, using the commands from Task 2 verbatim:
  1. **What you get:** the asset list.
  2. **Quick verify:** `gh release download agent-vX.Y.Z --repo …`, `sha256sum -c SHA256SUMS`, then `gh attestation verify` with `--repo`, `--signer-workflow` and `--source-ref refs/tags/agent-vX.Y.Z`.
  3. **Verify the SBOM attestation:** the same command with `--predicate-type https://cyclonedx.org/bom`.
  4. **Offline / air-gapped:** `gh attestation download <binary> --repo …`, `gh attestation trusted-root > trusted_root.jsonl`, then `gh attestation verify <binary> --bundle <file> --custom-trusted-root trusted_root.jsonl --repo …`.
  5. **What provenance proves, and what it doesn't:** copy the spec's anti-goal wording.
  6. **Trust root:** GitHub Actions OIDC, Sigstore Fulcio short-lived certificates, the Rekor transparency log; no key held by the repo.
  7. **When a new CVE drops:** find the stdlib/module versions with `jq` on `<binary>.cdx.json`; run `govulncheck -mode binary <binary>`.
  8. **Detecting tampering after publication:** a changed asset no longer matches the attested digest, and the Rekor entry is append-only.
  9. **Cosign:** optional; it can verify the same Sigstore bundle; not required.

  Mark the commands with `X.Y.Z` placeholders, and show `0.1.0` as the example.

- [ ] **Step 2: Replace `agent_release_signing.md` with a stub.** The stub keeps the title, says "Superseded by S1 on <merge date>; the GPG flow never ran and was removed", and links `agent_release_verification.md`. Delete the GPG instructions.

- [ ] **Step 3: Repoint the links.**
  - `agent/README.md`: describe attested releases and link `../docs/security/agent_release_verification.md`. This fixes the mismatched link text.
  - `docs/security/agent_enrollment.md:43`: change the link target.
  - `docs/README.md:21`: list the new doc, with the signing doc as "superseded stub".
  - `README.md:126-133`: say the agent ships as attested releases with a CycloneDX SBOM, and link the doc. Don't claim a release exists until Stage B. Write "the release workflow produces …" and leave the URL for Stage B.
  - `docs/agent_auto_update.md:3`: append "The GPG manifest model below must be replaced by artifact attestations (see security/agent_release_verification.md) before this is revisited."

- [ ] **Step 4: Check every link.**
  - `git -C C:/dev/ht-s1-a grep -n "agent_release_signing"`. Expected: hits only in the stub's own references, `docs/README.md`, and the untouched historical docs (`month_4_execution_plan.md`, `roadmap-review-2026-09.md`, `agent_auto_update.md`, if they still reference it), all resolving to the existing stub path `docs/security/agent_release_signing.md`.
  - Expected: zero hits for the wrong root path `docs/agent_release_signing.md` outside `roadmap-review-2026-09.md`, which quotes it as a historical finding.

- [ ] **Step 5: Commit:** `docs(security): agent release verification guide; retire the GPG signing doc`.

### Task 4: Stage A review, PR and proof runs (controller)

- [ ] **Step 1: Review.** One `reviewer-risk` pass (default Sonnet) on `origin/main...HEAD`. The focus is permissions per job, injection through `${{ }}` in `run:`, verify not being vacuous, rehearsal cleanup, pins, and the doc commands matching the workflow. At most 2 fix rounds, re-reviewed by Haiku for a small diff. If it's still failing after round 2, stop and ask Arlo.
- [ ] **Step 2: Push.** Check `gh auth status` (`firegiant9000` active), then `git -C C:/dev/ht-s1-a push origin feat/s1-a-agent-release:refs/heads/feat/s1-a-agent-release`.
- [ ] **Step 3: Open a draft PR.** `gh pr create --draft --base main` with the title `S1 Stage A: attested agent release workflow, SBOM, verification doc`. The body covers:
  - the pins table;
  - the per-job permissions;
  - the rulings: the rehearsal name and `--source-ref` in every mode;
  - the failure-handling note (Review Focus 5);
  - the overlap note with #219;
  - the settings recommendations.

  Check `baseRefName == main`. Wait for PR CI to go green. The new `check_sbom` tests run in `Scan exceptions and workflow pins`.
- [ ] **Step 4: Ask Arlo for the two dispatches** from the branch, or for a permission rule:
  - `gh workflow run agent-release.yml --repo firegiant9000/Senior-Cybersecurity-Project --ref feat/s1-a-agent-release`;
  - the same with `-f rehearse=true`.
- [ ] **Step 5: Read both runs.** Expected:
  - the plain run: `build` and `verify` green, `publish` and `cleanup` skipped;
  - the rehearsal: `build`, `publish`, `verify` and `cleanup-rehearsal` green, and the tamper self-test logged as failing verification. After it, `gh release list` is empty and `git ls-remote --tags origin` is empty.

  Record both run URLs, plus one attestation URL from the build summary, in the PR body. If a draft or tag is left over, stop and tell Arlo; deleting it is their call.
- [ ] **Step 6: Stop** for Arlo to mark the PR ready and merge it.

## Stage B: the release (after Stage A merges)

### Task 5: Tag `agent-v0.1.0` and record the evidence (controller; Arlo's go-ahead required)

- [ ] **Step 1: Check before asking.** `origin/main` contains the Stage A merge; `ScannerVersion` is `"0.1.0"` on `origin/main`; `gh release list` and `git ls-remote --tags origin` are empty.
- [ ] **Step 2: Ask Arlo for an explicit go-ahead to push the tag.** Only after a yes: `git -C C:/dev/ht-s1-a fetch origin`, `git -C C:/dev/ht-s1-a tag agent-v0.1.0 origin/main`, `git -C C:/dev/ht-s1-a push origin refs/tags/agent-v0.1.0`. The tag is lightweight and on the merge commit. If the classifier denies the push, Arlo pushes it themselves.
- [ ] **Step 3: Watch the tag run** to green. Expected: `build`, `publish`, `verify` (including the tamper self-test and the undraft) succeed; `cleanup-rehearsal` is skipped; the release is public and not a prerelease.
- [ ] **Step 4: Verify manually from this machine.** Run `gh release download agent-v0.1.0` into the scratchpad, then the doc's quick-verify commands verbatim. Expected: both `gh attestation verify` calls report verified, and `sha256sum -c` (Git Bash) reports OK.
- [ ] **Step 5: Record the evidence in the ledger:**
  - the release URL;
  - the attestation URLs, with the Rekor log index from `gh attestation verify --format json`;
  - the SBOM asset URL;
  - the verify job log URL;
  - the manual verify output, summarised.

### Task 6: Close-out (draft PR to `main`; Obsidian)

**Files:**
- Modify: `docs/PRODUCT_VIABILITY_ROADMAP.md` (the `#### S1` section)
- Modify: `README.md` (the agent release paragraph: add the release URL)

- [ ] **Step 1: Mark S1 DONE in the roadmap.** Add the PR numbers, the date, links to the release, the verify run and the doc, and fill in the résumé line exactly as the roadmap words it, now true.
- [ ] **Step 2: Add the release link to `README.md`.**
- [ ] **Step 3: Gate, review and open the PR.** Gate with a docs-only link grep. One `reviewer-logic` pass (docs only). Push and open a draft PR to `main` (base checked).
- [ ] **Step 4: Update Obsidian** (`Senior-Cybersecurity-Project/`):
  - `decisions.md`: a 2026-10-2X S1 section covering the dry run instead of the as-is tag, `actions/attest` direct, `cyclonedx-gomod`, the draft → verify → publish flow, and cosign out.
  - `todos.md`: tick the binary-govulncheck item; add the settings recommendations as Arlo items.
  - `gotchas.md`: anything new from the runs.
  - Never write secrets or identifiers.
