# Hacker Tracker Agent — Read-Only Host Scanner (Linux)

A small, dependency-free Go binary that collects a **read-only** inventory of a
Linux host — installed packages, running services, and (optionally) listening
ports — and uploads it to the Hacker Tracker backend under a per-host enrollment
token. The backend matches the inventory against CVE/KEV data and surfaces
findings in the dashboard.

This is the **Month 4 Phase 4** deliverable. The wire contract it emits is frozen
in `backend/app/schemas/agent_scan.py` (`schema_version "1.0"`) and validated by
the shared golden fixture `backend/tests/fixtures/agent_scan_v1.json`.

---

## What it collects

| Category | Source | Notes |
|---|---|---|
| Host metadata | `os.Hostname()`, `uname -m`, `/etc/os-release` | hostname, arch, OS name/version |
| Primary IP | local route to a public address (no packet sent) | best-effort |
| Installed packages | `dpkg-query` (Debian/Ubuntu) **or** `rpm -qa` (RHEL/Fedora) | name + version (+ vendor on rpm) |
| Running services | `systemctl list-units --type=service --state=running` | unit name + state |
| Listening ports | `ss -tulpen` | **only** with `--include-ports` |

### What it does NOT collect

The scanner is read-only and intentionally narrow. It **never**:

- reads file **contents**, documents, or source code,
- reads environment variables, secrets, tokens, or credentials,
- reads browser history, cookies, or saved passwords,
- writes, modifies, installs, or removes anything on the host,
- makes outbound connections except the single upload to the server you specify.

You can always inspect exactly what would be sent with `scan --print` **before**
uploading anything.

---

## Supported distributions

| Distro family | Package manager | Status |
|---|---|---|
| Debian / Ubuntu | `dpkg` | ✅ supported |
| RHEL / Fedora / CentOS / Rocky / Alma | `rpm` | ✅ supported |
| Anything else (Alpine `apk`, Arch `pacman`, …) | — | ❌ **not supported in v1** |

On an unsupported distro the scanner prints a warning to stderr and emits an
empty `software` list rather than silently reporting "0 packages". Windows is
Month 5; macOS is Month 6.

---

## Build

```sh
cd agent
go build ./cmd/hacker-tracker        # produces ./hacker-tracker
# or cross-compile for a Linux target:
GOOS=linux GOARCH=amd64 go build -o hacker-tracker ./cmd/hacker-tracker
GOOS=linux GOARCH=arm64 go build -o hacker-tracker-arm64 ./cmd/hacker-tracker
```

The module is **stdlib-only** — no third-party dependencies, to keep the
supply-chain / code-signing surface (Phase 5) minimal.

`make agent-build-all` (from the repo root) mirrors the CI release build:
version-stamped, stripped, cross-compiled `linux/amd64`+`arm64` with a
`SHA256SUMS` manifest. Tagged releases (`agent-vX.Y.Z`) are built, GPG-signed, and
published to GitHub Releases by `.github/workflows/agent-release.yml`; see
[../docs/agent_release_signing.md](../docs/security/agent_release_signing.md) for the
signing and verification flow.

## Test

```sh
cd agent
go test ./...
```

The collector parsers and the output shape are unit-tested. `internal/output`
round-trips the golden fixture, asserting the Go struct stays in lockstep with
the backend's frozen contract (no extra/renamed/dropped fields).

---

## Usage

```sh
# Show everything that would be sent — review before uploading.
hacker-tracker scan --print

# Save to a file.
hacker-tracker scan --output inventory.json

# Include listening ports (off by default).
hacker-tracker scan --include-ports --print

# Upload to the backend under an enrollment token.
hacker-tracker scan --upload \
  --server https://api.example.com \
  --api-key ht_<prefix>_<secret>
```

Flags (`hacker-tracker scan --help`):

| Flag | Env | Description |
|---|---|---|
| `--print` | — | Print JSON to stdout (default if no action given) |
| `--output <file>` | — | Write JSON to a file (mode `0600`) |
| `--upload` | — | Upload to the backend |
| `--include-ports` | — | Also collect listening TCP/UDP ports (needs `ss`) |
| `--server <url>` | `HT_SERVER` | Backend base URL, e.g. `https://api.example.com` |
| `--api-key <token>` | `HT_API_KEY` | Agent enrollment token `ht_<prefix>_<secret>` |
| `--timeout <dur>` | — | HTTP timeout for upload/poll (default `30s`) |

---

## Enrollment & lifecycle

The token is a **per-host** bearer credential minted in the dashboard
(Settings → Agents). It is shown **once** at enrollment time and stored hashed
server-side — there is no "show it again". Treat it like an SSH key. The
user-facing walkthrough (enroll → install → rotate → revoke → lost host) is in
[../docs/agent_enrollment.md](../docs/security/agent_enrollment.md).

1. **Enroll** — in the dashboard, *Enroll new agent*; copy the `ht_…` token.
2. **Install** — drop the binary on the host and run `scan --upload` with the token
   (e.g. from cron or a systemd timer).
3. **Verify** — the dashboard's agent list shows `last_used_at` updating after the
   first successful scan.
4. **Rotate** — *Rotate* issues a new token; the old one stays valid for a 24h
   grace window so you can swap it without downtime.
5. **Revoke / lost host** — *Revoke* immediately invalidates the token; a revoked
   token gets `401` on the next upload.

### Transport & replay

- Uploads go to `POST {server}/api/v1/inventory/scans` with
  `Authorization: Bearer ht_<prefix>_<secret>` over **HTTPS only**.
- Each upload carries a fresh `scan_id` (UUIDv4) and `nonce`; the backend rejects
  a duplicate `(scan_id, nonce)` within 24h (`409`), so a captured payload cannot
  be replayed.

### Upload responses the scanner handles

| HTTP | Meaning | Scanner behavior |
|---|---|---|
| `201` | Accepted | Prints the `scan_run` id and polls its status |
| `401` | Token rejected (bad/revoked/expired) | Clear error, exit 1 |
| `409` | Duplicate / replay | Clear error, exit 1 |
| `422` | Payload/schema rejected | Clear error, exit 1 |
| `426` | Scanner below server's minimum version | "please upgrade" message, exit 1 |

---

## Contract / schema drift

`internal/output/json.go` is the Go mirror of the backend `AgentScanPayload`.
The backend uses `extra="forbid"`, so this binary must never emit a field the
backend doesn't know. If the contract changes:

1. Bump `schema_version` on the backend **and** `SchemaVersion` here.
2. Update `backend/tests/fixtures/agent_scan_v1.json` and the copy in
   `agent/internal/output/json_test.go`.
3. Add the new version to the backend's `SUPPORTED_SCHEMA_VERSIONS`.
