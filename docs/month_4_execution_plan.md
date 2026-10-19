# Month 4 Execution Plan — Read-Only Host Scanner MVP (Linux) + Agent Trust Model

> **Status 2026-09-29: HISTORICAL, merged (PR #172).** The "uncommitted on branch" note below is out of date. Reclassified follow-ups: the Phase 0 entry gate is CANCELLED; Phase 5 (signing and release) never ran and is SUPERSEDED by S1 (keyless attestations and an SBOM); Phase 6 auto-update is DEFERRED; wiring persisted ports into the exposed-port risk factor is DEFERRED; the `agents.ts` Vitest is OPTIONAL. The agent's trust model is the input to the S3 threat model. Current plan: [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md).

> **Status: code-complete on all 7 phases; uncommitted on `feature/month4-scanner-agent-plan` (review 2026-06-13).** Phases 1–7 are implemented (agent trust model, enrollment API + UI, scan-upload endpoint, Go Linux scanner, signing/CI, auto-update doc, privacy + retention). Two post-review fixes are applied: the scan-history retention cliff (now time-window + safety ceiling) and the unbounded `agent_scan_nonces` table (now purged in the retention sweep). **The Phase 0 entry gate remains OPEN — see [month_4_phase0_closeout.md](month_4_phase0_closeout.md); the team has accepted that risk in writing (Phase 0 closeout, "Risk acceptance").** This document decomposes Month 4 of [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md) into numbered phases and supersedes the roadmap's Month 4 task tables. Open follow-ups: wire the persisted ports into the internet-exposed-port risk factor (Month 5; the ports/services themselves are now persisted on the asset), and add a Vitest for `frontend/src/api/agents.ts`.
>
> **Headline finding:** the backend ingestion path is already **agent-ready**. `ScanSource` and `DiscoveredVia` literals already include `"agent"`; `commit_inventory()` takes a `source` parameter; the matcher trigger, `scan_runs` table, `audit_log` helpers, and the slowapi rate limiter all exist and are directly reusable. The genuinely greenfield work is narrower than the roadmap implies: **(1) the agent trust model (non-Firebase bearer-token auth), (2) the Go scanner binary + Linux collectors, (3) code-signing + a release pipeline, (4) the auto-update design doc.** Do not rebuild the inventory ingestion plumbing — call into it.

---

## Entry gates (must pass before any scanner code)

Month 4 is the only month with **two gates in front of it**. Do not write scanner code until both are satisfied — the roadmap put them here specifically to prevent building an agent nobody will install.

### Checkpoint 2 — Month 3 matcher quality gate (must already be passed)
- Regression set ≥95% pass; high-confidence FP rate <2% — ✅ met on `feature/month3-cpe-matching-plan` (51 cases, 100%, 0 high-confidence FPs).
- **⏳ Open (process, not code):** ≥1 interviewee has reviewed sample findings and judged them useful. **This is still outstanding per the Month 3 plan** and gates entry to Month 4.

### Checkpoint 3 — Scanner build entry gate (roadmap, Month 4 entry)
**Proceed only if:**
- Checkpoint 2 passed (including the interview evidence above).
- ≥2 real users (interviewees / prospective pilots) explicitly say they would test a read-only inventory agent.
- Privacy/data-handling pages live **and updated for the agent** (today they say "we do not install agents" — see Phase 0).
- Code-signing cert procurement **initiated** (2–3 week calendar lead time — start day 1, Phase 0).

**Stop or pivot if:** users will not install a third-party agent under any conditions, OR the CSV/SBOM + M365 workflow alone proves sufficient for pilots, OR signing/distribution complexity outweighs demand → **skip the scanner; reallocate Month 4 to Google Workspace OAuth + report polish** (both already queued as Month 2→3 carryovers). If this branch fires, the trust-model backend (Phases 1–3) is still worth shipping for a future agent; only Phases 4–6 are dropped.

---

## Current state (what already exists — reuse, do not rebuild)

| Roadmap Month 4 item | Actual status | Evidence |
|---|---|---|
| Scan ingestion source `"agent"` | ✅ Already a literal | `schemas/scan_run.py` `ScanSource = Literal["csv_upload","m365","gws","agent"]`; `schemas/asset.py` `DiscoveredVia` includes `"agent"` |
| Inventory commit path | ✅ Reusable as-is | `services/inventory_import.py::commit_inventory(session, *, org_id, rows, scan_run_id, source)` — pass `source="agent"` |
| `scan_runs` table + repo | ✅ Exists | `db/scan_run.py`, `repositories/scan_runs.py` (status/source/counts/error_message/metadata) |
| Trigger matching after upload | ✅ Exists | `workers/matcher_job.py::trigger_matcher_async(org_id, trigger=...)` — call with `trigger="agent_scan"` |
| Audit log + write helpers | ✅ Exists | `db/audit_log.py`; `_audit()` in `inventory.py`, `_write_audit_log_and_flush()` in `data_lifecycle.py` |
| Rate limiting | ✅ Exists | `core/limiter.py` (slowapi) + `settings.RATE_LIMIT_DATA` applied on inventory routes |
| Retention policy | ✅ Stub only | `services/retention.py` (`RetentionPolicy`: 12 scans/asset, 365-day audit window); **sweep is a no-op — Month 4 wires the cron** |
| Privacy / data-handling pages | ⚠️ Exist but **wrong** | `docs/privacy.md`, `PrivacyPage.tsx`, `DataHandlingPage.tsx` state "we do **not** install agents" — must be rewritten for the agent before Checkpoint 3 |
| Firebase auth | ✅ Exists (humans only) | `core/dependencies.py::get_current_user` / `require_role`; `HTTPBearer` Firebase verification in `auth.py` |

### What is genuinely MISSING (the real Month 4)

1. **Agent trust model / non-Firebase auth.** No `agent_enrollments` table, no `services/agent_token.py`, no bearer dependency that validates an agent token (vs. a Firebase ID token). This is the hard backend piece.
2. **Agent enrollment API + UI.** No `routes/v1/agents.py` (enroll/rotate/revoke/list), no `schemas/agent.py`, no org-settings enrollment screen.
3. **Scanner upload endpoint.** No `POST /inventory/scans` that authenticates by agent token, validates a versioned scan payload, detects replays, and routes through `commit_inventory`.
4. **The Go scanner itself.** No `agent/` directory, no Go anywhere in the repo (`go.mod`, collectors, JSON output, upload client all greenfield).
5. **Code-signing + release pipeline.** No `.github/workflows/agent-release.yml`; no Go build step in CI; no cert.
6. **Auto-update design doc.** No `docs/agent_auto_update.md`.
7. **Retention sweep cron.** Stub exists; never scheduled.

### Existing branch / PR findings (per investigation rule 6)
- No branch or open PR touches the agent, scanner, enrollment tokens, or Go. Greenfield.
- Migration HEAD is **047** (`047_add_finding_software_identity.py`); new migrations start at **048**.
- Carryovers that intersect Month 4's stop/pivot branch: Google Workspace OAuth, CycloneDX SBOM (#115), M365 `detectedApps` software-level discovery.

---

## Phased plan

**Dependency order:** Phase 0 (gate) → **Phase 1 → 2 → 3** are the backend critical path. **Phase 4** (Go scanner) depends only on the *frozen upload contract* from Phase 3, not its full implementation — freeze the JSON schema early so the scanner and endpoint build in parallel. **Phases 5 (signing/CI), 6 (auto-update doc), 7 (privacy/retention/docs)** are parallelizable. **Phase 5's cert procurement must start in Phase 0** (calendar critical).

```
Phase 0 (gate + cert kickoff + privacy rewrite)
   │
   ├─▶ Phase 1 (agent_enrollments + token service + bearer auth)  ← blocks backend
   │       └─▶ Phase 2 (enroll/rotate/revoke API + org-settings UI)
   │       └─▶ Phase 3 (scan upload endpoint + replay + versioned schema)
   │                 │ freeze upload contract ──┐
   │                 ▼                          ▼
   │            (matcher reuse)          Phase 4 (Go scanner + Linux collectors)
   │
   ├─▶ Phase 5 (code-signing + agent-release.yml)   ── parallel, cert started in P0
   ├─▶ Phase 6 (docs/agent_auto_update.md design)   ── parallel
   └─▶ Phase 7 (privacy/transparency pages, retention cron, enrollment docs) ── parallel
```

### Phase 0 — Entry gate, trust-model decisions, cert kickoff (½–1 day, gate)
*Owner: lead dev + validation lead. Nothing downstream starts until this clears.*

> **Status: PARTIALLY CLEARED** — see [month_4_phase0_closeout.md](month_4_phase0_closeout.md). Steps 2 (trust-model frozen) and 4 (migration head 047→048) done. Steps 1 (validation gates) and 3 (cert order) are open human actions and block Phase 1.

1. **Confirm both gates** (Checkpoint 2 interview evidence + Checkpoint 3's ≥2 "would install" users). Record in `docs/validation_interviews.md`. If the stop/pivot criteria fire, switch to the GWS-OAuth + report-polish track and stop here.
2. **Settle the trust-model decisions** (roadmap table — these must be frozen before Phase 1 code):
   - One token **per agent** (per-host revocation), not per org.
   - Store **hash only** (`token_hash`) + display **prefix** (`token_prefix`); never persist the raw secret.
   - Transport: `Authorization: Bearer ht_<prefix>_<secret>` over **HTTPS only**.
   - Replay protection: payload carries `scan_id` (UUID) + `nonce`; reject duplicates within 24h.
   - Default expiry 365 days, per-org configurable; rotation issues a new token with a **24h grace** on the old.
   - Identity is `(org_id, agent_id)`, **never hostname** (hostnames collide).
   - Mark agents inactive after **30 days** no-contact; surface in admin UI.
3. **Kick off code-signing cert procurement (calendar critical — do this on day 1).** Windows EV cert is 2–3 weeks of lead time and needs a hardware token; Apple Developer ID ($99/yr) for the Month 6 macOS path. Phase 5 cannot finish without it; the rest of Month 4 can.
4. Confirm migration head = **047**; first new migration is **048**.
- **Exit:** both gates pass in writing; trust-model table ratified; cert order placed.

### Phase 1 — Agent trust model: data layer + token service + bearer auth (backend, critical path)
*Owner: lead dev. Blocks Phases 2 and 3. Hardest backend piece.*

> **Status: IMPLEMENTED.** Migration 048 (`agent_enrollments`, unique index on `token_prefix`), `services/agent_token.py` (sha256 hash-only, `hmac.compare_digest`, prefix-collision retry, rotation grace, expiry), `repositories/agent_enrollments.py`, `get_agent_from_token` in `core/dependencies.py` (separate scheme from `get_current_user`), and `schemas/agent.py`. Unit-tested in `tests/test_agent_token.py`.

1. **Migration 048** — `agent_enrollments` table per the roadmap data model: `id`, `org_id`, `token_hash`, `token_prefix`, `name`, `scopes` (JSON), `created_by_user_id`, `created_at`, `last_used_at`, `revoked_at`, `expires_at`. Index `(org_id)` and `token_prefix`.
2. **`services/agent_token.py`** — issue / verify / rotate / revoke:
   - Generate a high-entropy secret; format `ht_<prefix>_<secret>`; store `sha256(secret)` as `token_hash`, `prefix` as `token_prefix`. Return the raw token **once** at issue time (never retrievable again — mirror how SSH/PAT systems behave).
   - `verify(raw_token)` → resolve by prefix, constant-time compare the hash, reject if `revoked_at`/`expires_at`/grace-expired; bump `last_used_at`.
   - `rotate` issues a new token, keeps the old valid for a 24h grace window.
3. **`repositories/agent_enrollments.py`** following the established repo pattern (`Depends(get_session)` factory, `org_id`-scoped reads).
4. **Agent bearer dependency** in `core/dependencies.py` (e.g. `get_agent_from_token`) — a **separate** auth scheme from `get_current_user`; an agent token must never satisfy a human-only route and vice-versa. Returns the resolved enrollment (org_id + scopes) for use in Phase 3.
5. **`schemas/agent.py`** — `AgentCreate`, `AgentRead` (prefix + last_used_at + status, never the secret), `AgentListResponse`, `AgentTokenIssued` (the one-time raw-token response).
- **Verification:** unit tests for token issue/verify/rotate/revoke incl. grace window, expiry, revocation, and constant-time mismatch; assert the raw secret never round-trips out of the DB.
- **Risk:** a leaked or replayed token = cross-host data injection. Hash-only storage + per-agent revocation + replay nonce (Phase 3) are the mitigations.

### Phase 2 — Enrollment API + org-settings UI (backend + frontend)
*Depends on Phase 1. Parallel with Phase 3.*

> **Status: IMPLEMENTED.** `routes/v1/agents.py` (enroll/list/rotate/revoke, **`require_org_role("admin")`** — tighter than the originally-planned global `require_role("admin")`, audited), `frontend/src/api/agents.ts`, and the enrollment panel in `SettingsPage.tsx`. Backend tests in `tests/test_agent_routes.py`. **Open follow-up:** no Vitest for `agents.ts` (Month 3 set that precedent).

1. **Routes** (`routes/v1/agents.py`, all `require_role("admin")`, Firebase-authed humans):
   - `POST /api/v1/agents/enroll` — exchange a one-time enrollment code for a token (returns raw token once).
   - `POST /api/v1/agents/{id}/rotate` — rotate; old valid 24h.
   - `DELETE /api/v1/agents/{id}` — revoke.
   - `GET /api/v1/agents` — list org agents with `last_used_at`, status (active / stale-30d / revoked).
2. **Audit** every enroll/rotate/revoke via the existing `_audit()` helper (`agent.enroll`, `agent.rotate`, `agent.revoke`).
3. **Frontend** — agent enrollment panel in `SettingsPage.tsx` (or a new `AgentsPage.tsx` linked from settings): list agents + status, "Enroll new agent" → show the raw token **once** with a copy-and-install snippet, rotate/revoke buttons. New `frontend/src/api/agents.ts`.
- **Verification:** an admin can enroll, see the token once, install it, see `last_used_at` update after the first scan, and revoke it; non-admins get 403; cross-org enrollment IDs 404.

### Phase 3 — Scanner upload endpoint + replay + versioned schema (backend, critical path)
*Depends on Phase 1 (agent auth). Reuses `commit_inventory` + `trigger_matcher_async`. Freeze the payload schema here so Phase 4 can build against it.*

> **Status: IMPLEMENTED.** `POST /inventory/scans` + `GET /inventory/scans/{id}` in `inventory.py` (agent-authed, org derived from token), frozen `schemas/agent_scan.py` (`extra="forbid"`), `services/agent_scan.py` (version gates + payload→rows), replay nonce with a DB unique-constraint backstop (migration 049, `agent_scan_nonces`) recorded in the import transaction, per-token rate-limit key (`agent_token_key`). Tests in `tests/test_agent_scan_routes.py` / `test_agent_scan_service.py`. **Update (2026-06-13):** `services` and `ports` are now **persisted** as replace-on-scan JSON snapshots on `assets.services` / `assets.listening_ports` (migration 050), surfaced in the asset-detail response, and only overwritten when a scan actually reports the field (so CSV/M365 assets are untouched). Wiring the persisted ports into the Month 3 risk scorer's "internet-exposed port" factor remains Month 5.

1. **`POST /api/v1/inventory/scans`** authenticated by the **agent bearer dependency** (Phase 1), not Firebase. Derive `org_id` from the enrollment — the agent cannot assert an arbitrary org.
2. **Versioned JSON schema validation** (`schema_version` field; reject unknown/unsupported versions with a clear error). Validate OS/hostname/arch/software[]/services[]/ports[] shapes.
3. **Replay detection** — reject a payload whose `(scan_id, nonce)` was seen in the last 24h (store a short-TTL record or a unique constraint with a cleanup sweep).
4. **Store as `scan_run`** with `source="agent"`, `scanner_version`, `raw_payload_hash`; map software rows through **`commit_inventory(..., source="agent")`** (reuse) → assets/asset_software.
5. **Trigger matching** via `trigger_matcher_async(org_id, trigger="agent_scan")` (reuse).
6. **`GET /api/v1/inventory/scans/{scan_run_id}`** for the agent to poll status.
7. **Rate-limit per token** (new `settings.RATE_LIMIT_AGENT_UPLOAD` via `core/limiter.py`); **scanner min-version enforcement** (reject below `MIN_AGENT_VERSION`); **audit** each upload (`inventory.agent_scan`).
- **Verification:** a hand-crafted scan JSON uploads under a real token → persisted `scan_run` (source=agent) → assets/software → findings appear after the matcher runs; replayed payload is rejected; below-min version is rejected; revoked token is 401.
- **Risk:** schema drift between scanner and backend. Mitigate with the explicit `schema_version` and a golden-payload fixture shared by Phase 3 tests and Phase 4 output tests.

### Phase 4 — Go scanner binary + Linux collectors (greenfield, parallel once contract frozen)
*Owner: scanner OS-coverage owner. Depends on the frozen Phase 3 payload contract, not its implementation.*

> **Status: IMPLEMENTED.** `agent/` skeleton, Linux collectors (dpkg/rpm/systemctl/ss),
> CLI (`scan --print/--output/--upload/--include-ports`), and the upload client are in
> place; output is the Go mirror of the frozen `schema_version "1.0"` contract and is
> unit-tested against the shared golden fixture. **Verification gap:** Go is not
> installed in the dev environment used to author this, so `go build`/`go test` have not
> been run here — run `make agent-test && make agent-build` on a box with Go ≥1.22 (and
> the end-to-end `--upload` smoke on a real Linux host) to close Phase 4.

1. **`agent/` skeleton** at repo root (peer to `backend/`/`frontend/`): `go.mod`, `cmd/hacker-tracker/main.go`, `internal/collectors/{os,software_linux,ports}.go`, `internal/output/json.go`, `internal/upload/client.go`, `README.md`, `examples/inventory.sample.json`.
2. **Linux collectors** (stable APIs, ~1 week): `dpkg-query` (Debian/Ubuntu), `rpm -qa` (RHEL/Fedora), `systemctl` services, `ss -tulpen` (ports, behind `--include-ports`). **Read-only**; never read file contents, browser history, secrets, env vars, or documents.
3. **CLI**: `scan --print` (show everything before upload), `scan --output inventory.json`, `scan --upload --api-key <enrollment_token>`, `scan --include-ports`. Emit the **frozen schema_version**.
4. **Upload client** posts to `POST /inventory/scans` with the bearer token + `scan_id`/`nonce`; honors min-version rejection gracefully.
- **Verification:** on a Linux box `scan --print` lists installed packages/services; `--upload` lands a `scan_run` and findings appear in the UI; output validates against the Phase 3 golden fixture. Document every collected field in `agent/README.md`.
- **Risk:** distro variance. Scope Month 4 to dpkg + rpm only; document unsupported distros explicitly (no silent gaps). Windows = Month 5, macOS = Month 6.

### Phase 5 — Code-signing + agent-release.yml (CI/release, parallel; cert started in Phase 0)

> **Status: IMPLEMENTED (signing key/cert pending — see below).** `.github/workflows/agent-release.yml`
> builds linux/amd64+arm64 (version stamped via `-ldflags`, `-trimpath`, static),
> generates `SHA256SUMS`, GPG-signs the manifest, and publishes a GitHub Release on
> `agent-v*` tags. A Go `agent` job (vet/gofmt/test/build) was added to `ci.yml`
> (closes the "no Go build step in CI" gap). Signing flow is documented in
> [agent_release_signing.md](security/agent_release_signing.md); macOS notarization and Windows
> Authenticode are stubbed there. **Open:** Linux uses **GPG over SHA256SUMS**, not the
> EV cert (the cert mainly unblocks Month 5 Windows per the risk table). Until
> `AGENT_SIGNING_GPG_KEY` is configured, releases publish as **unsigned prereleases for
> internal pilots only** (the documented fallback). To close Phase 5: configure the
> signing key secret and cut a tagged release that produces a signed, downloadable
> binary.

1. ~~Once the EV cert lands:~~ `.github/workflows/agent-release.yml` builds the Go binary (linux/amd64 + arm64), signs the release artifact (GPG over `SHA256SUMS`), publishes to GitHub Releases. **(Done — Linux uses GPG signing; EV/Authenticode deferred to Month 5.)**
2. Document the signing flow; stub the macOS notarization step (deferred to Month 6). **(Done — [agent_release_signing.md](security/agent_release_signing.md).)**
- **Verification:** a tagged release produces a signed, downloadable Linux binary from CI.
- **Risk:** cert lead time. Mitigated by ordering on day 1; if the cert slips, ship an **unsigned** Linux binary to internal pilots only and gate public distribution on the signature (Linux tolerates unsigned far better than Windows — the EV cert mainly unblocks Month 5 Windows).

### Phase 6 — Auto-update design doc (design only, parallel)

> **Status: IMPLEMENTED (design doc).** [agent_auto_update.md](agent_auto_update.md)
> covers poll-vs-push (recommends **poll** for v1 — no push command channel),
> the signed update manifest (reuses the Phase 5 **GPG-over-`SHA256SUMS`** primitive,
> no new keys), the verify-before-swap update sequence, crash-on-startup rollback via
> a watchdog + `.prev` fallback, per-org/host version pinning, and stable/beta
> channels with staged rollout. **Design only — no code in Month 4.** **Open:** team
> review of the four questions in the doc's "Open questions" section.

`docs/agent_auto_update.md` (2–3 pages, team-reviewed): poll-vs-push, signed update manifest format, crash-on-startup rollback, per-org version pinning for change-control customers, stable/beta channels. **Design only — implementation is Month 5/6.** It must exist before v1 ships because auto-update is painful to retrofit onto already-deployed agents.

### Phase 7 — Privacy/transparency, retention cron, enrollment docs (parallel; privacy is an entry-gate prerequisite)

> **Status: IMPLEMENTED (with two post-review fixes applied 2026-06-13).** Privacy/data-handling pages rewritten for the agent; retention sweep scheduled in `workers/scheduler.py` (`RETENTION_SWEEP_SCHEDULE`); `docs/agent_enrollment.md` + `docs/manual_test_month4.md` written.

1. **Rewrite the privacy/data-handling surfaces** (`docs/privacy.md`, `PrivacyPage.tsx`, `DataHandlingPage.tsx`) — they currently claim "we do not install agents." Add a scanner-transparency section: exactly what the agent collects (and the explicit **does-not-collect** list), read-only guarantee, `--print` before upload. **Blocks Checkpoint 3, so land the copy early.**
2. **Wire the retention sweep** — schedule `services/retention.py::run_retention_sweep` in `workers/scheduler.py`. **Post-review fix:** the original "latest 12 scan_runs per org" cap was a data-loss cliff (each agent host = 1 run/scan, so a multi-host org lost the history the Month 5 month-over-month report needs). Now **time-window primary** (`SCAN_RUN_RETENTION_DAYS`, default 400 — covers 13 months) **+ a high per-org safety ceiling** (`MAX_SCAN_RUNS_PER_ORG`, default 2000), plus a 365-day audit-log window. The sweep also **purges expired `agent_scan_nonces`** (`< now − AGENT_SCAN_REPLAY_WINDOW_HOURS`), closing the unbounded-growth gap where `purge_before()` existed but was never called.
3. **Document the enrollment + revocation flow** for users (`agent/README.md` + `docs/agent_enrollment.md`): install, enroll, rotate, revoke, what to do on a lost host.
- **Verification:** privacy pages render the agent disclosure; a manual `manual_test_month4.md` smoke script (mirroring `manual_test_month3.md`) walks enroll → scan → findings → revoke. Retention behavior is covered by CI (needs Postgres; not runnable in the doc-author env).

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Leaked/replayed agent token → cross-host injection | Hash-only storage, per-agent revocation, 24h replay nonce, `(org_id,agent_id)` identity, HTTPS-only |
| Agent token satisfies a human route (or vice-versa) | Separate auth dependency/scheme; agent tokens never resolve `get_current_user` |
| Users won't install a third-party agent | Checkpoint 3 gate fires *before* scanner code; pivot to GWS OAuth + report polish, keep the trust-model backend |
| Code-signing cert lead time (2–3 wks) | Order on day 1 (Phase 0); ship unsigned Linux to internal pilots; cert mainly unblocks Month 5 Windows |
| Scanner ↔ backend schema drift | Explicit `schema_version`; golden-payload fixture shared by Phase 3 + Phase 4 tests |
| Privacy pages contradict the new agent | Phase 7 rewrite is gated *before* the build (Checkpoint 3) |
| Distro variance in Linux collectors | Scope to dpkg + rpm; document unsupported distros; no silent gaps |
| Migration drift on a head at 047 | Start at 048 (used 048 + 049); CI `alembic check` already guards drift |
| Scan-history retention too aggressive → loses MoM-report history | ✅ Fixed: time-window primary (400d) + high per-org safety ceiling (2000), replacing the 12-runs-per-org cliff |
| Unbounded `agent_scan_nonces` growth | ✅ Fixed: retention sweep purges nonces older than the replay window (`purge_before` now wired) |
| Building Phases 1–7 before the Phase 0 gate passes | Risk **accepted in writing** — see [month_4_phase0_closeout.md](month_4_phase0_closeout.md) "Risk acceptance"; trust-model backend (P1–3) survives a pivot, only P4–6 would be at risk |

## Test plan
- **Unit:** token issue/verify/rotate/revoke + grace/expiry (P1); scan payload validation + replay rejection + min-version (P3); risk-scorer reuse unaffected.
- **Integration:** enroll → upload scan under token → `commit_inventory` → matcher → persisted findings (P2/P3); revoked/expired token → 401; cross-org enrollment ID → 404.
- **Scanner:** Go collector unit tests + output validates against the shared golden fixture (P4).
- **Security:** agent token cannot reach human routes; human token cannot hit `/inventory/scans`; replayed `(scan_id,nonce)` rejected.
- **Manual:** `docs/manual_test_month4.md` end-to-end (Linux box → enroll → scan → findings → rotate → revoke).

## Month 4 exit / Month 5 entry gate (roadmap Checkpoint 4 setup)
Month 4 is done when: the Linux scanner collects inventory, `--print` shows it, `--upload` lands assets/software/findings via a per-agent bearer token, tokens rotate/revoke, the audit log records every enroll/rotate/revoke/upload, privacy pages disclose the agent, the auto-update design doc is reviewed, and the code-signing cert is in hand or in flight. This sets up **Checkpoint 4 (end of Month 5): ≥1 external pilot runs the scanner end-to-end.**

## Recommended phase ordering summary
```
Phase 0 (gate, trust decisions, cert order, privacy rewrite kickoff)
   ├─▶ Phase 1 (agent_enrollments + token service + bearer auth)  [critical path]
   │      ├─▶ Phase 2 (enroll/rotate/revoke API + UI)
   │      └─▶ Phase 3 (scan upload + replay + versioned schema) ──┐ freeze contract
   │                                                              ▼
   │                                                         Phase 4 (Go scanner + Linux collectors)
   ├─▶ Phase 5 (code-signing + agent-release.yml)   [parallel; cert from P0]
   ├─▶ Phase 6 (agent_auto_update.md design)        [parallel]
   └─▶ Phase 7 (privacy/transparency, retention cron, enrollment docs)  [parallel; privacy gates Checkpoint 3]
```
