# Verifying an Agent Release (milestone S1)

> How to check that a Hacker Tracker agent binary was built by this repository's
> release workflow ([agent-release.yml](../../.github/workflows/agent-release.yml))
> before you run it on a host. Replaces the retired GPG flow
> ([agent_release_signing.md](agent_release_signing.md)).

Commands use `X.Y.Z` placeholders; the example version is `0.1.0`, so the tag is
`agent-v0.1.0` and the binary is `hacker-tracker-0.1.0-linux-amd64`. You need the
GitHub CLI (`gh`) with `gh attestation` support, signed in (`gh auth login`).

## What you get

Each release `agent-vX.Y.Z` carries five assets:

| Asset | What it is |
|---|---|
| `hacker-tracker-X.Y.Z-linux-amd64` | Static scanner binary |
| `hacker-tracker-X.Y.Z-linux-arm64` | Static scanner binary |
| `hacker-tracker-X.Y.Z-linux-amd64.cdx.json` | CycloneDX SBOM of the amd64 binary |
| `hacker-tracker-X.Y.Z-linux-arm64.cdx.json` | CycloneDX SBOM of the arm64 binary |
| `SHA256SUMS` | Checksums of the four files above |

Both binaries have a SLSA build provenance attestation and a CycloneDX SBOM
attestation, stored with GitHub and logged in the Sigstore transparency log.

## Quick verify

```sh
gh release download agent-vX.Y.Z --repo firegiant9000/Senior-Cybersecurity-Project
sha256sum -c SHA256SUMS
gh attestation verify hacker-tracker-X.Y.Z-linux-amd64 \
  --repo firegiant9000/Senior-Cybersecurity-Project \
  --signer-workflow firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml \
  --source-ref refs/tags/agent-vX.Y.Z \
  --deny-self-hosted-runners
```

Example: `X.Y.Z` = `0.1.0`. A pass prints the verified attestation and exits 0. Any
failure (exit non-zero) means do not run the binary. `sha256sum -c` only catches
corruption; the attestation check is the one that ties the file to this workflow.

`--signer-workflow` pins the workflow that signed, `--source-ref` pins the tag it
ran on, and `--deny-self-hosted-runners` rejects builds from runners other than
GitHub-hosted ones. Do not drop them: bare `gh attestation verify --repo …` accepts
any workflow in the repo on any ref.

## Verify the SBOM attestation

Same command with the SBOM predicate type:

```sh
gh attestation verify hacker-tracker-X.Y.Z-linux-amd64 \
  --repo firegiant9000/Senior-Cybersecurity-Project \
  --signer-workflow firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml \
  --source-ref refs/tags/agent-vX.Y.Z \
  --deny-self-hosted-runners \
  --predicate-type https://cyclonedx.org/bom
```

This proves an SBOM was attested for that exact binary digest. The downloaded
`.cdx.json` and `SHA256SUMS` files are not themselves attested; only the SBOM
predicate inside the attestation is. Compare the downloaded `.cdx.json` with the
verified predicate (add `--format json`) if you need to confirm the file itself.

## Offline / air-gapped

Fetch the bundle and the trust root on a connected machine, then verify offline:

```sh
gh attestation download hacker-tracker-X.Y.Z-linux-amd64 --repo firegiant9000/Senior-Cybersecurity-Project
gh attestation trusted-root > trusted_root.jsonl
gh attestation verify hacker-tracker-X.Y.Z-linux-amd64 \
  --bundle <bundle-file>.jsonl \
  --custom-trusted-root trusted_root.jsonl \
  --repo firegiant9000/Senior-Cybersecurity-Project \
  --signer-workflow firegiant9000/Senior-Cybersecurity-Project/.github/workflows/agent-release.yml \
  --source-ref refs/tags/agent-vX.Y.Z \
  --deny-self-hosted-runners
```

`gh attestation download` writes a bundle named after the binary's digest,
`sha256:<digest>.jsonl` (`sha256-<digest>.jsonl` on Windows) in the current
directory; pass whichever file it wrote as `<bundle-file>.jsonl`. The trusted root rotates, so refresh it before
each offline verification session.

## What provenance proves, and what it doesn't

Proves: the binary was built by this repository's `agent-release.yml`, at the commit
and ref named in the attestation, on a GitHub-hosted runner.

Does not prove:

- that the source is free of bugs or backdoors;
- that the build is reproducible (it is not claimed to be);
- that the repository or the GitHub account was not itself compromised before the tag.

The SBOM is generated from the built binary, so it records the exact Go toolchain
(stdlib) version that shipped, not just the module graph.

## Trust root

- **GitHub Actions OIDC** identifies the workflow run (repo, workflow, ref, commit).
- **Sigstore Fulcio** issues a short-lived signing certificate bound to that identity;
  there is nothing long-lived to steal or rotate.
- **Rekor** (the transparency log) records each signature publicly and append-only.

The repository holds no signing key and the workflow reads no secrets.

## When a new CVE drops

Find out what a shipped binary contains from its SBOM:

```sh
# Go toolchain (stdlib) the binary was built with, e.g. go1.27.3
jq -r '.components[] | select(.name == "std") | .version' hacker-tracker-X.Y.Z-linux-amd64.cdx.json

# Agent version recorded in the SBOM, e.g. v0.1.0
jq -r '.metadata.component.version' hacker-tracker-X.Y.Z-linux-amd64.cdx.json

# All components and versions
jq -r '.components[] | "\(.name) \(.version)"' hacker-tracker-X.Y.Z-linux-amd64.cdx.json
```

Then check the binary itself for reachable vulnerabilities (the workflow runs the
same scan at release time, so this catches CVEs published since):

```sh
govulncheck -mode binary hacker-tracker-X.Y.Z-linux-amd64
```

If a stdlib CVE affects the shipped toolchain, cut a new release built with a fixed
Go; releases are not patched in place.

## Detecting tampering after publication

A modified asset no longer matches the digest in its attestation, so
`gh attestation verify` fails on it (the release workflow checks this on every
release by verifying a deliberately modified copy and requiring a failure). The
Rekor entry is append-only: an attacker with release-write access can replace an
asset, but cannot alter or remove the original signature record. Always verify
after download, not only once at release time.

## Cosign (optional)

The attestations are standard Sigstore bundles, so `cosign verify-blob-attestation`
can check the same bundle (from `gh attestation download`). It is not required and
not part of the supported flow; `gh attestation verify` is the acceptance check.

## macOS notarization (deferred)

Not part of this flow. The release ships Linux binaries only; macOS and Windows
signing is cancelled or deferred with their scanners.
