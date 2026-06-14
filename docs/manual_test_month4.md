# Manual end-to-end smoke test — Month 4 (read-only host scanner + agent trust model)

Mirrors [manual_test_month3.md](manual_test_month3.md). Until a Playwright suite
exists, the Month 4 Definition-of-Done — "Linux scanner collects inventory,
`--print` shows it, `--upload` lands assets/software/findings via a per-agent
bearer token, tokens rotate/revoke, the audit log records every
enroll/rotate/revoke/upload, privacy pages disclose the agent" — is verified
manually with this script. Run before tagging a Month 4 release candidate;
capture screenshots at each numbered step for the trust pack.

## Prereqs

- Local stack running: `make up` (postgres + backend + frontend).
- Month 3 matcher working (CPE criteria seeded — see `manual_test_month3.md`
  step 1), so an uploaded inventory produces findings.
- A Linux host (or container) with `dpkg`/`rpm` available, and the agent binary
  built for it (`cd agent && go build ./cmd/hacker-tracker`).
- An admin Firebase account.

## Steps

1. **Privacy disclosure renders.** Open `/privacy` and `/data-handling` in the
   app. Confirm:
   - `/privacy` no longer says "we do not install agents"; it shows **The
     optional host scanner** section with the collects / never-collects lists.
   - `/data-handling` shows the **Optional host scanner** note linking to
     `/privacy`.

2. **Enroll an agent.** As an admin, **Settings → Agents → Enroll new agent**.
   Confirm:
   - The raw `ht_<prefix>_<secret>` token is shown **once** with a copy snippet.
   - The agent appears in the list with status *active* and an empty
     `last_used_at`.
   - DB: `agent_enrollments` has a row with a `token_hash` (not the raw secret)
     and matching `token_prefix`.
   - Audit: an `agent.enroll` row exists in `audit_log`.

3. **Review before upload.** On the Linux host run
   `hacker-tracker scan --print`. Confirm it lists installed packages, running
   services, OS/host metadata — and **no** file contents, env vars, or secrets.
   With `--include-ports`, listening ports also appear; without it, they do not.

4. **Upload under the token.**
   `hacker-tracker scan --upload --server <url> --api-key ht_<prefix>_<secret>`.
   Confirm:
   - HTTP `201`; the CLI prints a `scan_run` id and polls its status to
     `succeeded`.
   - DB: a `scan_runs` row with `source='agent'`, `status='succeeded'`,
     populated `scanner_version` / `raw_payload_hash`.
   - **Assets** tab shows the host with an `Agent` source; **View** it →
     findings appear after the matcher runs (Month 3 pipeline).
   - The **Settings → Agents** list now shows `last_used_at` updated.
   - Audit: an `inventory.agent_scan` row exists.

5. **Replay is rejected.** Re-POST the exact same payload (same
   `scan_id`/`nonce`) within 24h. Confirm `409` and no duplicate `scan_run`.

6. **Below-min version is rejected.** Upload a payload stamped with a
   `scanner_version` below `MIN_AGENT_VERSION`. Confirm `426` ("please upgrade")
   and no `scan_run`.

7. **Auth isolation.**
   - A **human** Firebase token cannot hit `POST /inventory/scans` (rejected).
   - The **agent** token cannot reach a human-only route (e.g. `GET /agents`
     returns 401/403, not data).

8. **Rotate.** **Settings → Agents → Rotate**. Confirm a new token issues; the
   **old** token still uploads successfully within the 24h grace window; an
   `agent.rotate` audit row exists.

9. **Revoke / lost host.** **Settings → Agents → Revoke**. Confirm:
   - The next upload under that token returns `401`.
   - The agent shows *revoked* in the list.
   - An `agent.revoke` audit row exists.
   - Non-admins get `403` on enroll/rotate/revoke; a cross-org agent id `404`s.

10. **Retention sweep.** As an admin, `POST
    /api/v1/organizations/{org}/retention/run`. Confirm the response reports the
    policy and per-table `deleted` counts (`scan_runs`, `audit_log`). With >12
    scan_runs seeded for the org, confirm only the latest 12 survive. (The
    nightly `RETENTION_SWEEP_SCHEDULE` cron runs the same sweep across all orgs.)

## Pass criteria

- Privacy/data-handling pages disclose the agent (collects + never-collects).
- `scan --print` shows inventory and nothing sensitive; `--upload` lands a
  `source='agent'` scan_run → assets/software → findings.
- Replayed and below-min-version payloads are rejected; auth schemes are
  isolated both ways.
- Rotate honors the 24h grace; revoke `401`s immediately; every
  enroll/rotate/revoke/upload is audited.
- The retention sweep prunes to 12 scan_runs/org and the 365-day audit window.
