# S1: A real agent release, `agent-v0.1.0`, with SBOM and provenance — design

Date: 2026-10-21. Owner: Arlo Kharod. Roadmap: `docs/PRODUCT_VIABILITY_ROADMAP.md`, milestone S1.

## Intent

S1 ships the first public release of the read-only Linux host scanner (`agent/`) with keyless build provenance and an attested CycloneDX SBOM, and removes the secret-dependent GPG step that never ran.

1. **Portfolio evidence.** The roadmap's résumé line ("keyless build provenance (GitHub artifact attestations, Sigstore) and a CycloneDX SBOM, verifiable with `gh attestation verify`; replaced a secret-dependent GPG signing step") and its four interview questions (what provenance proves and doesn't; why keyless and what the trust root is; how a consumer uses the SBOM after a new CVE; how tampering after publication is detected) are the bar.
2. **A release a consumer can actually verify.** The release page, the consumer doc and a CI job all run the same verification commands, and they pass.

## Goals

- A public GitHub Release `agent-v0.1.0` (not a prerelease) with:
  - `hacker-tracker-0.1.0-linux-amd64` and `hacker-tracker-0.1.0-linux-arm64`;
  - one CycloneDX JSON SBOM per binary;
  - `SHA256SUMS` covering the binaries and the SBOMs;
  - a build-provenance attestation for each binary, and an SBOM attestation linking each SBOM to its binary.
- `gh attestation verify` passes in a CI `verify` job and in the documented manual steps.
- No signing secret in repository settings. Already true: `gh secret list` (2026-10-21) shows no `AGENT_SIGNING_GPG_*`. S1 removes every code and doc path that reads them.
- A binary-mode `govulncheck` scan of the built artifacts that blocks the release. This closes the S2 follow-up "govulncheck scans the source, not the released binaries".
- `docs/security/agent_release_verification.md`: the exact commands a consumer runs.
- No broken documentation links. The workflow and five docs point at `docs/agent_release_signing.md` (wrong path; the file is `docs/security/agent_release_signing.md`) or at the GPG flow.

## Non-goals

- Cosign keyless signing. Out (Arlo, 2026-10-21): artifact attestations already give keyless, Sigstore-backed signatures, and `gh attestation verify` is the acceptance check. The consumer doc may mention cosign as an alternative verifier of the same Sigstore bundle.
- Reproducible builds. Desirable, not required; don't claim it.
- macOS or Windows builds, notarization or Authenticode (cancelled or deferred).
- The agent auto-updater (`docs/agent_auto_update.md`, DEFERRED). Its GPG trust model stays as written, with one added note that it must be rebased on attestations when it's revisited.
- Repo settings: tag rulesets, immutable releases, required checks. Recommendations to Arlo only (see Settings recommendations); S1 code must not depend on them.
- Bumping `ScannerVersion`. It stays `"0.1.0"` (`agent/internal/output/json.go:32`).
- Revisiting S2: gates, the SHA-pin policy, the scan-exception checker, the S5a eval.

## Anti-goals (would be a failure even if CI is green)

- A public release that fails its own verification. The release must not become public before `verify` has passed against its assets.
- A verify job that is green because it doesn't really check: verifying against the wrong repo or signer, `continue-on-error`, or verifying the files it just built instead of the downloaded ones.
- A long-lived signing secret of any kind.
- `id-token: write` or `contents: write` granted at workflow level, or both granted to the same job when that's avoidable.
- An SBOM describing the source tree rather than what ships. It must be generated from the built binaries, so it records the exact Go toolchain (stdlib) version.
- An unpinned tool: every `uses:` SHA-pinned (`@<40-hex> # vX.Y.Z`, resolved with `gh api`), and every `go install` at an explicit version.
- Overstated claims in docs: say what provenance proves (built by this workflow, from this repo, at this commit and ref, on a GitHub-hosted runner) and what it doesn't (that the source is free of bugs or backdoors, or that the build is reproducible).

## Decisions

### Release path: dry runs first, one real tag (Arlo, 2026-10-21)

The roadmap's "tag as-is to learn what breaks" is replaced by a dispatch dry run. Tagging as-is would have published a public, unsigned prerelease and burned `0.1.0`.

- Done 2026-10-22: today's workflow dispatched on `main`, run 39717869999, green in 1m03s, no release. Learnings, all folded in below:
  - nothing functional broke;
  - Node 20 deprecation warnings on the pinned `checkout`, `setup-go` and `upload-artifact` majors;
  - `ubuntu-latest` is migrating to Ubuntu 26;
  - the unsigned-prerelease warning fires.
- The rewritten workflow is proven by dispatching it from the S1 branch (`gh workflow run agent-release.yml --ref <branch>`). GitHub runs the branch's copy of the file because a file of that name exists on `main`.
  - The auto-mode classifier blocks Claude from running `gh workflow run`, so Arlo dispatches, or adds a permission rule.
  - In a public repo, attestations go to the public Sigstore transparency log permanently. Dry-run attestations for `0.0.0-dev` binaries are accepted as harmless and honest.
- **The tag-only path is rehearsed** without pushing a tag (Arlo, 2026-10-22). A `workflow_dispatch` boolean input `rehearse` (default `false`) does four things:
  - runs `publish` against a **draft** release named `agent-v0.0.0-rehearsal-<run_id>`, created with `--target <github.sha>` and without `--verify-tag`;
  - runs `verify` against that draft's downloaded assets, with every check except the tag-specific `--source-ref`;
  - then **deletes the draft** (`gh release delete --yes`, plus `--cleanup-tag` as a guard) instead of undrafting it;
  - deletes the draft even when `verify` fails, using an `if: always()` cleanup step scoped to the rehearsal name.
- A draft release doesn't create a git tag. The builder confirms this in the first rehearsal run (`git ls-remote --tags origin` stays empty) and stops if it doesn't hold. Version stamping stays `0.0.0-dev`, and the `ScannerVersion` check doesn't run.
- The rehearsal is the gate for Stage A's PR. A throwaway public tag was considered and rejected: it's outward-facing, hard to reverse, and would need a `ScannerVersion` bypass.
- `agent-v0.1.0` is tagged once, on `main` after the Stage A merge, with Arlo's explicit go-ahead at that moment.

### Workflow shape (`.github/workflows/agent-release.yml`, rewritten)

Triggers: push of `agent-v*` tags; `workflow_dispatch` **without** the `ref` input (my call, from the builder check).

- The input let checkout build a different commit from the one the attestation records as the workflow's ref and SHA, which would make provenance name the wrong commit.
- Dry runs choose the commit with `gh workflow run --ref <branch>` instead.

Top-level `permissions: contents: read`.

**`build` job** (`runs-on: ubuntu-24.04`, pinned rather than `ubuntu-latest` so the build environment recorded in provenance doesn't shift with the Ubuntu 26 migration). Steps keep today's behaviour unless stated:

- Checkout (`persist-credentials: false`); setup-go `1.27` with `check-latest: true`, `cache: false`.
- Resolve the version; check the tag against `ScannerVersion` (tag runs only); vet and test; build both arches with `CGO_ENABLED=0 -trimpath -ldflags "-s -w -X …ScannerVersion=${VERSION}"`.
- **Binary-mode govulncheck**: `govulncheck -mode binary` on each built binary, blocking.
  - It uses the same pinned version as `security.yml` (`golang.org/x/vuln/cmd/govulncheck@v1.9.0`).
  - It applies no exceptions, matching `security.yml`'s govulncheck job.
- **SBOM**: `cyclonedx-gomod` (Arlo agreed to the outline 2026-10-21; chosen over syft because it is Go-native and reads module and toolchain data from the binary's build info).
  - Install it with `go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@vX.Y.Z`, at a version resolved at implementation time. `go install` with a version is checksum-verified against `sum.golang.org`.
  - Generate one CycloneDX JSON per binary from the binary (`bin` mode), named after the binary, e.g. `hacker-tracker-0.1.0-linux-amd64.cdx.json`.
  - The SBOM must contain the Go stdlib/toolchain version and the main module at the release version.
  - The module lives in `agent/`, and `agent-v0.1.0` isn't a Go submodule tag, so build info reports the main module as `(devel)`. Pass the release version explicitly (`-version` or the equivalent flag), and add a step that fails if the SBOM's main component version or Go version is missing or wrong (my call).
  - Build into a directory outside the git working tree (e.g. `$RUNNER_TEMP/dist`), so untracked output can't stamp `vcs.modified=true` (`+dirty`) into build info (my call).
- `SHA256SUMS` over the binaries and SBOMs.
- **Attestations**:
  - `actions/attest-build-provenance` over both binaries;
  - `actions/attest-sbom` once per binary, with its own SBOM.
  - Both run on tag and dispatch runs.
  - Job-level permissions: `contents: read`, `id-token: write`, `attestations: write`, plus any further scope that the pinned version's docs require (e.g. `artifact-metadata: write`), checked against the docs at implementation time (my call).
  - If the named wrappers are now thin shims over `actions/attest`, pinning `actions/attest` directly is acceptable (my call); record which in the PR.
- Upload `dist/*` as the run artifact (current `upload-artifact` major).

**`publish` job** (tag runs and `rehearse` dispatches; `needs: build`; `contents: write`; no `id-token`):

- Downloads the run artifact.
- Creates the release as a **draft** with `gh release create agent-vX.Y.Z --draft --verify-tag`, attaching every file. The body comes from a file or heredoc and uses absolute URLs.
- Drops `softprops/action-gh-release` and its pin.
- Not a prerelease. The macOS stub comment stays, repointed at the new doc.

**`verify` job** (`needs: build` on dispatch runs; `needs: publish` on tag runs):

- Gets the files the way a consumer would:
  - tag runs and `rehearse` dispatches: the draft release's assets via `gh release download`;
  - plain dispatch runs: the run artifact.
- Runs `sha256sum -c SHA256SUMS`.
- Runs, for each binary:
  - `gh attestation verify <binary> --repo firegiant9000/Senior-Cybersecurity-Project --signer-workflow firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml`;
  - the same command with `--predicate-type https://cyclonedx.org/bom`, to check the SBOM attestation;
  - on tag runs only, `--source-ref refs/tags/agent-vX.Y.Z` as well.
- Doesn't check out the repo's build output; it only consumes the downloaded files.
- **On tag runs, only after every check passes**, a final step undrafts the release with `gh release edit --draft=false`. The public release therefore never exists in an unverified state, and the flow is compatible with immutable releases if Arlo turns them on.
- **Permissions:** `verify` holds `contents: write` and never `id-token` (my call, from the builder check).
  - Draft releases are visible only to tokens with write access, so a read-only verify job couldn't download the draft.
  - The invariant is that no job holds both `id-token: write` and `contents: write`.
  - Undrafting therefore lives in `verify`, not in a separate job.
- **Draft lookup:** the download must find the draft. Look it up by release ID or by listing releases, if `gh release download <tag>` doesn't resolve drafts.
- **`gh` version:** print `gh --version`, and fail fast if it's older than the minimum supporting every flag used (e.g. `--source-ref`, `--signer-workflow`, `--predicate-type`) (my call).

### GPG path: removed

The `Check for signing key` and `Sign checksums (GPG)` steps, the `AGENT_SIGNING_GPG_*` references, the unsigned-prerelease logic and the GPG release-body text all go. There's nothing to delete in settings.

### Documentation

- **New:** `docs/security/agent_release_verification.md`, for consumers. It covers:
  - download (`gh release download agent-vX.Y.Z`);
  - `sha256sum -c`;
  - `gh attestation verify` for provenance and for the SBOM, with the same flags as the CI job;
  - an offline/air-gapped note (`gh attestation download` + `--bundle`, plus `gh attestation trusted-root`);
  - what the attestation proves and doesn't;
  - the trust root (GitHub's OIDC issuer + Sigstore Fulcio/Rekor; no repo-held key);
  - how to use the SBOM when a new CVE drops (query it for the module/stdlib version; re-run `govulncheck -mode binary` on the downloaded binary);
  - how tampering after publication is detected (a changed asset fails the digest match against the signed attestation; the Rekor entry is append-only).
- **`docs/security/agent_release_signing.md`:** replaced by a short "superseded" stub pointing at the new doc, so the historical links in `month_4_execution_plan.md` and `roadmap-review-2026-09.md` still resolve.
- **Repoint to the new doc:** `agent/README.md:69-71` (it also fixes the mismatched link text), `docs/security/agent_enrollment.md:43`, `docs/README.md:21`, and `README.md:128-131` (describe the shipped flow instead of "S1 will").
- **Leave the dated historical docs alone** (`month_4_execution_plan.md`, `roadmap-review-2026-09.md`, `hacker_tracker_6_month_development_plan.md`).
- **`docs/agent_auto_update.md`:** one line added to its existing DEFERRED status note; no rewrite.

### Action versions

S1 owns `agent-release.yml`'s action pins (Arlo, 2026-10-21). `checkout`, `setup-go`, `upload-artifact` and the new `download-artifact`, `attest-build-provenance` and `attest-sbom` go to current releases on Node 24.

- Resolve each SHA with `gh api` and record tag → SHA in the PR.
- Dependabot #219 also bumps these lines. Whichever lands second takes the other's newer pin, after a rebase or `@dependabot rebase`.

## Stages

- **Stage A, one draft PR to `main`:**
  - the spec, the workflow rewrite and the docs;
  - gated locally: actionlint if it can be pulled, otherwise a YAML parse; the pin grep from `security.yml`; agent `go vet`/`gofmt`/`go test` in `golang:1.27`; a local `cyclonedx-gomod bin` and `govulncheck -mode binary` run in the container on a locally built binary;
  - one `reviewer-risk` pass (CI, signing, permissions), at most 2 fix rounds;
  - then two dispatches from the branch (Arlo dispatches, or adds a permission rule for `gh workflow run`):
    - a plain dry run, with `verify` green against the run artifact;
    - a `rehearse: true` run, with `publish` → `verify` → draft deletion green, and no tag or release left behind;
  - both run links recorded in the PR body.
- **Stage B, after Stage A merges:**
  - Arlo's go-ahead, then tag `agent-v0.1.0` on `main` and push it;
  - record the release URL, the attestation (`gh attestation verify` output and the Rekor log index), the SBOM, the verify job log, and a manual `gh attestation verify` run from this machine;
  - close-out draft PR: roadmap S1 DONE with PR numbers and the résumé line; Obsidian decisions/todos/gotchas.

## Failure handling

- **If the tag run fails before undrafting**, the draft release isn't public. Fix forward:
  - delete the draft, and the tag if needed, only with Arlo's OK;
  - tag again, or move to `0.1.1` if the tag was already seen.
- **If `--verify-tag` or the `ScannerVersion` check fails**, nothing is published.
- **If binary-mode govulncheck finds a stdlib CVE at tag time**, the release waits for the fixing Go patch (`check-latest` picks it up), then the run is re-run (my call). There's no exception path for a release.

## Settings recommendations (Arlo's call; not part of S1's code)

- A tag ruleset restricting who can create or move `agent-v*` tags. Provenance records the commit, but verifiers should still pin `--source-ref`.
- Turn on immutable releases, so assets and tags can't change after publication. The draft-then-publish flow above is the pattern GitHub documents for it.
- Add the S2 required checks and the "Require code scanning results" rule. As of 2026-10-21 the `main` ruleset still requires only the 5 original checks.

## Left to the builder

- The exact action and tool versions (current releases, SHAs via `gh api`).
- The release-body wording (absolute URLs; it links the verification doc and states the Go version used).
- Whether `go test` gets `-race`; whether the SBOM also gets an `.spdx` form (not required).
