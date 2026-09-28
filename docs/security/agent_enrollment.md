# Host Scanner — Enrollment & Revocation Guide

User-facing guide for installing, enrolling, rotating, and revoking the
read-only host scanner (the Month 4 Linux agent). The technical reference for
the binary itself — flags, collected fields, distro support, schema contract —
lives in [../agent/README.md](../../agent/README.md). What the agent does and does
not collect is summarized on the in-app `/privacy` page and in
[privacy.md](privacy.md).

> **Opt-in and read-only.** Nothing is collected from a host until an admin in
> your org enrolls an agent and you run the binary on that host with its token.
> The scanner never writes, installs, or changes anything, and never reads file
> contents, secrets, credentials, or browser data. Run `scan --print` to see
> exactly what would be sent before uploading.

## Trust model at a glance

- **One token per host** (not per org), so a single host can be revoked without
  affecting the others.
- The token is shown **once** at enrollment and stored **hashed** server-side —
  there is no "show it again". Treat it like an SSH private key.
- Transport is `Authorization: Bearer ht_<prefix>_<secret>` over **HTTPS only**.
- Each upload carries a fresh `scan_id` + `nonce`; a replayed payload is rejected
  for 24h.
- Default token lifetime is 365 days. Rotation keeps the old token valid for a
  **24h grace window** so live hosts don't break mid-swap.
- Agents with no contact for **30 days** are surfaced as *stale* in the admin UI.

## 1. Enroll a new agent

Admins only (`require_role("admin")`).

1. In the dashboard go to **Settings → Agents**.
2. Click **Enroll new agent**, give it a recognizable name (e.g. the hostname).
3. Copy the `ht_<prefix>_<secret>` token shown **once**. Store it in your secret
   manager now — it cannot be retrieved again.

API equivalent: `POST /api/v1/agents/enroll` (returns the raw token once).

## 2. Install on the host

1. Download the signed Linux binary (see
   [agent_release_signing.md](agent_release_signing.md) for verifying the
   signature).
2. Review what will be sent, then upload:

   ```sh
   hacker-tracker scan --print                       # review first
   hacker-tracker scan --upload \
     --server https://api.example.com \
     --api-key ht_<prefix>_<secret>
   ```

3. Schedule recurring scans from cron or a systemd timer. Pass
   `--include-ports` only if you want listening ports collected.

## 3. Verify it's reporting

The **Settings → Agents** list shows each agent's `last_used_at` and status
(*active* / *stale (30d)* / *revoked*). After the first successful upload,
`last_used_at` updates and inventory/findings appear in the **Assets** tab.

## 4. Rotate a token

Routine hygiene, or when a token may have been exposed.

1. **Settings → Agents → Rotate** on the agent. Copy the new token.
2. Update the host (cron/timer/secret manager) with the new token.
3. The old token keeps working for **24h** — no downtime if you swap within the
   grace window.

API equivalent: `POST /api/v1/agents/{id}/rotate`.

## 5. Revoke / lost host

If a host is decommissioned, lost, or you suspect the token leaked:

1. **Settings → Agents → Revoke** on that agent.
2. The token is invalidated immediately; the next upload from it gets `401`.
3. Re-enroll a fresh agent if the host is being rebuilt — never reuse a revoked
   token.

API equivalent: `DELETE /api/v1/agents/{id}`.

Every enroll / rotate / revoke is recorded in the audit log (`agent.enroll`,
`agent.rotate`, `agent.revoke`), and each scan upload as `inventory.agent_scan`.

## Data retention

Scan history is pruned to the latest 12 runs per organization and audit entries
age out after 365 days, via the nightly retention sweep
(`RETENTION_SWEEP_SCHEDULE`). See [retention](../../backend/app/services/retention.py).
