# Agent Auto-Update — Design (Month 4 Phase 6)

> Phase 6 of [month_4_execution_plan.md](month_4_execution_plan.md). **Design only —
> no implementation in Month 4.** Auto-update ships in Month 5/6; this document
> exists now because the *contract* (manifest format, version source-of-truth,
> rollback behavior) is painful to retrofit onto agents that are already deployed
> in the field. Freezing it before v1 ships means the first released binary already
> knows where to look for updates and how to trust them.

## Scope and non-goals

**In scope (this doc):** the update *protocol* — how an installed agent learns a
newer version exists, verifies it is authentic, installs it, and recovers if the
new binary is broken. Plus the operator/customer controls (pinning, channels).

**Out of scope:** the implementation itself, a Windows/macOS updater (Months 5/6),
and any backend "push" infrastructure (see [Poll vs. push](#poll-vs-push) — we
recommend poll for v1, so there is little backend to build).

**Reuses, does not reinvent:**
- The signing primitive is the **same GPG-over-`SHA256SUMS`** scheme Phase 5
  already ships ([agent_release_signing.md](agent_release_signing.md)). The updater
  verifies an update the same way a human verifies a manual download — one signed
  manifest authenticates every artifact it lists. No second signing system.
- Distribution stays on **GitHub Releases** keyed by the `agent-vX.Y.Z` tag. The
  update manifest is just another release asset.
- The version source-of-truth remains `ScannerVersion` in
  [agent/internal/output/json.go](../agent/internal/output/json.go#L32) (a `var`,
  stamped at build time by the release pipeline), compared against the backend's
  `MIN_AGENT_VERSION` ([backend/app/core/config.py](../backend/app/core/config.py#L162)).

---

## Poll vs. push

| | Poll (agent checks on a timer) | Push (server tells the agent) |
|---|---|---|
| Backend work | None — reads a static manifest | New channel: long-lived connection or message bus |
| Firewall posture | Outbound HTTPS only (already required for upload) | Same, but needs a persistent inbound-style channel |
| Failure mode | Agent simply checks again next interval | Dropped connection → missed update; needs reconnect logic |
| Latency to roll an update | Minutes–hours (interval-bound) | Seconds |
| Fits our trust model | Yes — agent already initiates all contact | Adds an attack surface (server can command agents) |

**Decision: poll, for v1.** The scanner is a periodic, agent-initiated tool, not a
real-time service — there is no value in second-level update latency, and a push
channel would add a standing inbound command path that contradicts the Month 4
trust model (the agent initiates every connection; the server never commands a
host). The agent already makes outbound HTTPS calls to upload scans, so polling
adds no new network posture.

**Mechanics:** on each scan run (and at most once per `UPDATE_CHECK_INTERVAL`,
default 24h), the agent fetches the channel manifest, compares `latest` to its own
`ScannerVersion`, and — if newer and not pinned — performs the
[update sequence](#update-sequence). A scan is never blocked on the update check:
the check is best-effort and failures are logged, not fatal.

> The backend can still *advise* an update opportunistically: the upload client
> already sends `User-Agent: hacker-tracker-agent/<version>`
> ([agent/internal/upload/client.go](../agent/internal/upload/client.go#L73)). The
> server may return an advisory header (e.g. `X-Agent-Latest-Version`) on the scan
> response. This is a hint to shorten the next poll, **not** a push — the agent
> still pulls and verifies the manifest itself. HTTP 426 remains the hard floor
> (below `MIN_AGENT_VERSION` → upload rejected), independent of auto-update.

---

## Signed update manifest

One JSON manifest per channel, published as a GitHub Release asset and **covered by
the existing `SHA256SUMS` + detached GPG signature** — so verifying an update is
identical to verifying a manual download (`gpg --verify` the manifest signature,
then `sha256sum -c` the binary).

`agent-manifest-<channel>.json`:

```json
{
  "schema_version": "1.0",
  "channel": "stable",
  "latest": "0.3.0",
  "min_supported": "0.1.0",
  "released_at": "2026-07-15T00:00:00Z",
  "artifacts": [
    {
      "os": "linux",
      "arch": "amd64",
      "url": "https://github.com/firegiant9000/.../releases/download/agent-v0.3.0/hacker-tracker-linux-amd64",
      "sha256": "<hex>",
      "size_bytes": 8123456
    },
    {
      "os": "linux",
      "arch": "arm64",
      "url": "https://github.com/.../hacker-tracker-linux-arm64",
      "sha256": "<hex>",
      "size_bytes": 7984512
    }
  ],
  "rollout": { "percent": 100 },
  "notes_url": "https://github.com/.../releases/tag/agent-v0.3.0"
}
```

Field notes:
- `schema_version` — versions the **manifest format itself** (distinct from the
  scan payload's `schema_version`). The updater rejects manifest versions it does
  not understand and keeps the current binary.
- `min_supported` — if the running version is below this, the manifest may signal a
  forced upgrade (still subject to verification and rollback).
- `sha256` per artifact **must** match the value in the release's `SHA256SUMS`. The
  updater (a) verifies the GPG signature over `SHA256SUMS`, (b) confirms the
  manifest's `sha256` equals the manifest-listed checksum, (c) downloads the binary
  and checks its hash against `sha256` before it is ever made executable.
- `rollout.percent` — staged rollout (see [Channels](#release-channels-stable-beta)).

**Trust chain (no new keys):** `agent-manifest-*.json` and the binaries are listed
in the same `SHA256SUMS`; the detached `SHA256SUMS.asc` is the only signature. The
agent ships the signing **public** key baked in at build time (and re-pinned on each
update), so it can verify offline-style without trusting the transport. A manifest
or binary whose hash is not in a validly-signed `SHA256SUMS` is rejected — full
stop, current binary stays.

---

## Update sequence

Atomic, verify-before-swap, with the old binary retained for rollback:

1. **Fetch** the channel manifest; parse and validate `schema_version`.
2. **Compare** `latest` vs. `ScannerVersion`. If not newer, or the host is
   [pinned](#per-org-version-pinning), stop.
3. **Honor staged rollout** — deterministically bucket this host (hash of a stable
   per-host id) and skip if outside `rollout.percent`.
4. **Download** the matching `(os, arch)` artifact and the release's `SHA256SUMS` +
   `SHA256SUMS.asc` to a temp dir.
5. **Verify**: `gpg --verify` the manifest signature → `sha256sum -c` the downloaded
   binary against `SHA256SUMS` → confirm it equals the manifest `sha256`. Any
   failure aborts and deletes the temp download.
6. **Stage**: write to `hacker-tracker.new`, `chmod +x`, then run
   `hacker-tracker.new --version` as a **self-check** (must print the expected
   semver and exit 0).
7. **Swap atomically**: rename current binary to `hacker-tracker.prev`, rename
   `.new` → `hacker-tracker` (same-filesystem `rename(2)`, atomic).
8. **Record** the update (old/new version, timestamp) to a small state file next to
   the binary for the rollback watchdog.

Privilege note: the agent typically runs from a system path (e.g.
`/usr/local/bin`). In-place self-replacement needs write access there; if absent,
the updater logs that an update is available and exits cleanly rather than failing
the scan — operators using a package manager or config-management tool update
out-of-band, and `MIN_AGENT_VERSION`/426 still protects the backend.

---

## Crash-on-startup rollback

A new binary that immediately crashes is the worst auto-update failure: it can take
a fleet offline with no human in the loop. Guard with a **watchdog + previous-binary
fallback**:

- The `hacker-tracker.prev` binary from step 7 is the rollback target.
- A small **sentinel** records "version X installed at T, not yet confirmed
  healthy." A run is *confirmed healthy* once it completes a scan (or a
  `--version` + minimal self-check) without crashing.
- On startup the binary checks the sentinel: if the previous boot of *this* version
  did not reach "healthy" within N attempts (default 2), it **rolls back** —
  rename `hacker-tracker.prev` → `hacker-tracker`, mark the bad version
  `quarantined` so the updater will not re-install it until a strictly newer
  version supersedes it, and log loudly.
- The rollback path itself must not require network or the manifest (the host may
  be exactly why the update failed) — it is a local file rename only.

This bounds blast radius to "one failed scan interval, then back to the
last-known-good binary," with no operator action required.

---

## Per-org version pinning

Change-control customers (regulated environments, maintenance windows) cannot accept
silent upgrades. Two pinning layers, agent-local first so it works even offline:

1. **Host/agent-local pin** — a config field (`pinned_version` /
   `auto_update: false`). The updater respects it unconditionally. This is the
   floor: an operator can always freeze a host.
2. **Org-level pin (future, server-advised)** — the backend may return a per-org
   target/floor (e.g. on the scan response) so an admin pins "all our agents stay on
   0.2.x" from the dashboard. The agent treats this as advice layered over its local
   pin; the local pin always wins for safety. This rides the same trust model as the
   existing `AGENT_TOKEN_*` settings ([config.py](../backend/app/core/config.py#L150))
   and would be a small additive backend field — **not built in Month 4.**

Pinning suppresses normal upgrades but **never** suppresses
[crash rollback](#crash-on-startup-rollback) (safety) and never lets a host fall
below `MIN_AGENT_VERSION` without the operator seeing the 426 rejection — pinning
below the server floor surfaces as "upgrade required," not a silent failure.

---

## Release channels (stable / beta)

- **`stable`** — the default channel every agent tracks unless configured otherwise.
- **`beta`** — opt-in (`channel: beta` in config) for the team and willing pilots to
  shake out a build before it is promoted to `stable`.

Each channel is its own manifest (`agent-manifest-stable.json`,
`agent-manifest-beta.json`) pointing at the same release artifacts — promotion is
just publishing the beta version into the stable manifest. Combined with
`rollout.percent`, this gives: cut `agent-vX.Y.Z` → beta channel 100% → soak →
stable channel at 10% → 50% → 100%. A bad build is contained to beta or the early
rollout bucket, and the [rollback](#crash-on-startup-rollback) watchdog catches
crash-loops within those buckets.

---

## Configuration surface (proposed — for Month 5 implementation)

Agent-side config (file + flags), none implemented in Month 4:

| Key | Default | Purpose |
|---|---|---|
| `auto_update` | `true` | Master on/off for the poll-and-update loop. |
| `channel` | `stable` | `stable` or `beta`. |
| `pinned_version` | _(unset)_ | Freeze to an exact version; disables upgrades. |
| `update_check_interval` | `24h` | Minimum spacing between manifest polls. |
| `manifest_base_url` | GitHub Releases | Where channel manifests are fetched. |

Backend-side (future, advisory only): a per-org target/floor field and the
`X-Agent-Latest-Version` advisory header. No push channel, no new auth scheme —
auto-update introduces **no** new server-issued commands to agents.

---

## Open questions for team review

1. **Self-update privilege.** Do we support in-place self-replacement at all for
   v1, or recommend package-manager / config-management delivery and keep the agent
   "advise only"? (Affects whether the agent needs write access to its own path.)
2. **Stable per-host id for rollout bucketing** — reuse the enrollment identity, or
   a separate locally-generated UUID? (Must be stable across updates and must not
   leak into the scan payload, which is identified by `(org, token)` only.)
3. **Forced-upgrade UX** when a host is both pinned *and* below `min_supported` —
   loud warning vs. override the pin. Current lean: never override the pin silently;
   surface the 426 and let the operator act.
4. **Beta access control** — open opt-in vs. gated to enrolled pilot orgs.

---

## Status

**Design complete; implementation deferred to Month 5/6** per the execution plan.
This satisfies Phase 6's exit criterion: a team-reviewed auto-update design exists
before v1 ships. Next action is team review of the four open questions above; no
code lands for this phase in Month 4.
