# Agent Release & Code-Signing Flow (Month 4 Phase 5)

> **Status 2026-09-29: SUPERSEDED by milestone S1** of [PRODUCT_VIABILITY_ROADMAP.md](../PRODUCT_VIABILITY_ROADMAP.md). The flow below has never run: there are no tags and no releases. S1 replaces the secret-dependent GPG step with keyless GitHub artifact attestations and an attested CycloneDX SBOM, verified by `gh attestation verify`. This file stays until S1 lands and `agent_release_verification.md` replaces it. The macOS notarization stub is CANCELLED with the macOS scanner.

> Phase 5 of [month_4_execution_plan.md](../month_4_execution_plan.md). Covers how the
> read-only Linux scanner (`agent/`) is built, signed, and published, and stubs the
> macOS notarization path deferred to Month 6.

## TL;DR

- **Trigger:** push a tag `agent-vX.Y.Z`. CI ([.github/workflows/agent-release.yml](../../.github/workflows/agent-release.yml))
  builds `linux/amd64` + `linux/arm64`, generates `SHA256SUMS`, signs it with GPG,
  and publishes a GitHub Release.
- **Signing primitive (Linux, Month 4):** a **GPG detached signature over the
  `SHA256SUMS` manifest**. One signature authenticates every artifact it lists.
  Linux distribution convention — *not* Windows Authenticode.
- **No signing key configured?** The release still publishes, but as a
  **prerelease marked "unsigned — internal pilots only."** This is the documented
  fallback while the cert/key is procured; do not distribute unsigned builds
  publicly.
- **Windows EV cert / Authenticode** is a **Month 5** concern; **Apple Developer ID
  notarization** is **Month 6**. Both are stubbed below, not implemented here.

## Why GPG over SHA256SUMS (and not the EV cert) for Month 4

The execution plan's risk table is explicit: the Windows EV code-signing cert
"mainly unblocks Month 5 Windows," has a 2–3 week lead time, and "Linux tolerates
unsigned far better." Month 4 ships **Linux only**, where the established trust
mechanism is a signed checksum manifest verified against a published public key —
exactly what Authenticode is *not*. So Phase 5 implements GPG signing now and
leaves Authenticode for when the Windows agent (and its cert) lands.

## Cutting a release

1. **Bump the version in source.** Edit `ScannerVersion` in
   [agent/internal/output/json.go](../agent/internal/output/json.go). This is the
   value emitted in every scan payload and gated by the backend's
   `MIN_AGENT_VERSION` ([backend/app/core/config.py](../../backend/app/core/config.py)).
   The release job **fails** if the git tag and this source value disagree.
2. **Verify locally:** `make agent-test` then `make agent-build-all` (mirrors the CI
   build: version-stamped, stripped, cross-compiled, with `SHA256SUMS`).
3. **Tag and push:**
   ```sh
   git tag agent-v0.2.0
   git push origin agent-v0.2.0
   ```
4. CI builds, signs (if the key is configured), and creates the GitHub Release.
5. **Dry run without releasing:** run the workflow via *Actions → Agent Release →
   Run workflow* (`workflow_dispatch`). It builds and uploads run artifacts but
   never creates a release.

The version is stamped into the binary at build time with
`-ldflags "-X .../internal/output.ScannerVersion=<semver>"`; `ScannerVersion` is a
`var` (not a `const`) for exactly this reason. Builds are `-trimpath` + `-s -w` and
`CGO_ENABLED=0` for reproducible, static binaries.

## Verifying a downloaded release

```sh
# Import the signing public key once (published with the release as
# hacker-tracker-signing-key.pub.asc, or out-of-band from the team).
gpg --import hacker-tracker-signing-key.pub.asc

# Verify the manifest signature, then the binaries against the manifest.
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS
```

A good `gpg --verify` plus a passing `sha256sum -c` means the binary you have is
byte-for-byte what CI built and signed.

## Required CI secrets

| Secret | Required? | Purpose |
|---|---|---|
| `AGENT_SIGNING_GPG_KEY` | for **signed** releases | ASCII-armored **private** signing key (`gpg --armor --export-secret-keys <KEYID>`). Absent → unsigned prerelease. |
| `AGENT_SIGNING_GPG_PASSPHRASE` | only if the key has one | Passphrase, passed via `--pinentry-mode loopback`. |

`GITHUB_TOKEN` (auto-provided) covers the release upload via the job's
`contents: write` permission.

### Generating and registering the signing key

```sh
# Generate a dedicated signing key (not your personal key).
gpg --quick-generate-key "Hacker Tracker Agent Releases <agents@example.com>" ed25519 sign 2y

# Export the private key for the CI secret (store this value in
# AGENT_SIGNING_GPG_KEY — repo or org secret).
gpg --armor --export-secret-keys <KEYID>

# Export the public key to distribute to verifiers / commit to the repo.
gpg --armor --export <KEYID>
```

Store the private key only in GitHub Secrets and an offline backup; never commit
it. Publish the **public** key for downstream verification.

## Unsigned-pilot fallback (current state)

Per [month_4_phase0_closeout.md](../month_4_phase0_closeout.md) Step 3, the code-signing
cert is **not yet ordered**, and the GPG signing key may not be configured yet.
Until `AGENT_SIGNING_GPG_KEY` is set, the workflow:

- emits a CI warning,
- still builds and checksums the binaries,
- publishes them as a **GitHub prerelease** whose notes say "UNSIGNED — internal
  pilots only."

This unblocks internal pilot distribution without weakening the public-distribution
guarantee. Flip a release to general availability only once it is signed.

## macOS notarization (deferred — Month 6)

Stubbed in the workflow as commented steps. When the macOS collectors and an Apple
**Developer ID Application** certificate are in hand:

1. Build `darwin/amd64` + `darwin/arm64`.
2. `codesign --timestamp --options runtime --sign "Developer ID Application: …"`.
3. Zip and submit: `xcrun notarytool submit <zip> --apple-id … --team-id … --wait`.
4. Staple the ticket: `xcrun stapler staple <binary>`, then attach to the release.

Notarization requires the Apple Developer ID cert ($99/yr) tracked in the Phase 0
closeout — order before Month 6, not Month 4.

## Windows Authenticode (deferred — Month 5)

The Windows EV code-signing cert (hardware-token, 2–3 week lead) was ordered in
Phase 0 specifically to unblock the **Month 5** Windows agent. When that build
exists, add a Windows job that `signtool sign /fd sha256 /tr <timestamp-url>` the
`.exe` with the EV cert. Out of scope for Month 4 (Linux-only).
