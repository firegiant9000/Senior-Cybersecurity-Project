# Month 4 — Phase 0 Closeout (Entry gate, trust-model freeze, cert kickoff)

> Phase 0 of [month_4_execution_plan.md](month_4_execution_plan.md). This is the
> ratification record. Nothing in Phases 1–7 starts until the **gate status**
> below reads PASS in writing. The **trust-model table** here is frozen — Phase 1
> code (migration 048, `services/agent_token.py`, the agent bearer dependency)
> implements exactly these decisions; changing them means changing this doc first.

**Status: PROCEEDING UNDER ACCEPTED RISK.** Steps 2 (trust-model freeze) and 4
(migration head) are complete. Steps 1 (both validation gates) and 3 (cert order)
remain **open human actions**. The team has chosen to build Phases 1–7 in parallel
rather than block on them, and has **accepted that risk in writing** — see
[Risk acceptance](#risk-acceptance-issue-1--building-ahead-of-the-gate) below. The
open actions are not cancelled; they are still required before any external pilot
exposure.

---

## Step 1 — Gate status (BLOCKER)

Per the plan's two entry gates. Evidence lives in
[validation_interviews.md](validation_interviews.md).

| Gate | Requirement | Status | Evidence / gap |
|---|---|---|---|
| Checkpoint 2 (code) | Regression ≥95% pass, high-conf FP <2% | ✅ PASS | 51 cases, 100%, 0 high-conf FPs on `feature/month3-cpe-matching-plan` |
| Checkpoint 2 (process) | ≥1 interviewee reviewed **sample findings** and judged them useful | ⛔ OPEN | No interview records a findings review. Interview 1 endorsed the *concept* of a one-page report, but never saw real findings output. |
| Checkpoint 3 | ≥2 real users explicitly say they'd test a **read-only inventory agent** | ⛔ NOT MET (0 of 2) | Only 1 interview on file; it never asked about installing an agent. |
| Checkpoint 3 | Privacy/data-handling pages updated **for the agent** | ⛔ OPEN | [privacy.md](security/privacy.md) still says "we do not install agents." Fixed in Phase 7, which must land before this gate flips. |
| Checkpoint 3 | Code-signing cert procurement **initiated** | ⛔ OPEN | See Step 3. |

**Action required before Phase 1 code:**
1. Run ≥1 interview where the interviewee reviews actual sample findings (clears Checkpoint 2 process item).
2. Run ≥2 interviews that explicitly ask "would you install a read-only inventory agent?" and get a yes (clears Checkpoint 3).
3. Record all of the above in `validation_interviews.md` with verbatim answers.

**Stop/pivot check:** the pivot to GWS-OAuth + report polish fires only if users
say they will **not** install an agent under any conditions. We do not have that
signal — we have *no* signal yet. So the correct state is **gate-pending**, not
pivot. Do not abandon the scanner track; gather the evidence.

---

## Step 2 — Trust-model decisions (FROZEN)

Ratified for Phase 1. Each row is a binding contract for the implementation.

| # | Decision | Rationale |
|---|---|---|
| 1 | One token **per agent** (per host), not per org | Enables per-host revocation without nuking every agent |
| 2 | Store **`token_hash` (sha256) + `token_prefix`** only; raw secret never persisted | A DB leak cannot reveal usable tokens; mirrors SSH key / PAT behavior |
| 3 | Raw token returned **once** at issue time, never retrievable again | No "show me the token again" endpoint — forces re-issue on loss |
| 4 | Transport: `Authorization: Bearer ht_<prefix>_<secret>`, **HTTPS only** | Prefix routes the DB lookup; secret is the bearer proof |
| 5 | Replay protection: payload carries `scan_id` (UUID) + `nonce`; **reject duplicate `(scan_id, nonce)` within 24h** | Stops a captured payload from being re-injected |
| 6 | Default expiry **365 days**, per-org configurable | Bounds blast radius of a forgotten token |
| 7 | Rotation issues a new token; old token valid for a **24h grace** window | Zero-downtime key rotation on live hosts |
| 8 | Identity is **`(org_id, agent_id)`**, never hostname | Hostnames collide and are attacker-controllable |
| 9 | Mark agent **inactive after 30 days** no-contact; surface in admin UI | Operational hygiene; flags dead/removed hosts |
| 10 | Agent auth is a **separate dependency** from `get_current_user` | An agent token must never satisfy a human route, and vice-versa |

**`agent_enrollments` columns frozen for migration 048** (Phase 1 step 1):
`id`, `org_id`, `token_hash`, `token_prefix`, `name`, `scopes` (JSON),
`created_by_user_id`, `created_at`, `last_used_at`, `revoked_at`, `expires_at`.
Indexes: `(org_id)` and `token_prefix`.

---

## Step 3 — Code-signing cert procurement (BLOCKER — calendar critical)

Order on day 1; 2–3 week lead time. Phase 5 cannot finish without it; Phases 1–4 can proceed once gates pass.

| Cert | Purpose | Cost | Lead time | Status | Owner |
|---|---|---|---|---|---|
| Windows EV code-signing | Unblocks Month 5 Windows agent; hardware token required | varies | 2–3 weeks | ⛔ NOT ORDERED | _lead dev_ |
| Apple Developer ID | Month 6 macOS notarization path | $99/yr | days | ⛔ NOT ORDERED | _lead dev_ |

Linux (the Month 4 target) tolerates unsigned binaries for internal pilots, so a
cert slip does **not** block Phase 4 — but the order must be **placed** to satisfy
Checkpoint 3, and it gates Phase 5's public release.

---

## Step 4 — Migration head (CONFIRMED)

- Current head: **047** (`047_add_finding_software_identity.py`), single head — no
  branch points to it as a `down_revision`. ✅
- First new migration: **048** (Phase 1, `agent_enrollments`).
- `alembic check` in CI guards against drift.

---

## Risk acceptance (Issue 1 — building ahead of the gate)

**Decision (2026-06-13): the team proceeds with implementing Month 4 Phases 1–7
while the Phase 0 validation gate (Step 1) and cert order (Step 3) remain open. The
risk of this sequencing is accepted in writing, with the guardrails below.**

### What is being accepted
The plan's rule was "Phase 1 may begin only when all four exit rows read ✅." We are
knowingly overriding that ordering. The unmet items at decision time:
- Checkpoint 2 (process): no interviewee has reviewed actual sample findings.
- Checkpoint 3: **0 of 2** prospective users have confirmed they would install a
  read-only inventory agent.
- Checkpoint 3: code-signing cert not yet ordered.

### Why the risk is acceptable
1. **The signal is absent, not negative.** The stop/pivot trigger is users saying
   they *will not* run an agent under any conditions. We have no such signal — we
   have *no* signal yet. Building is a bet on a neutral prior, not against a
   negative one.
2. **The expensive layer is pivot-proof.** Phases 1–3 (the agent trust model:
   tokens, enrollment, the scan-ingest endpoint) are reused by *any* push-based
   ingestion source and survive a pivot to OAuth/agentless. Only Phases 4–6 (the Go
   scanner, signing, release pipeline) are scanner-specific and would be shelved.
3. **Schedule.** Parallelizing the backend build against validation keeps Month 4
   on its timeline; serializing would idle the critical-path backend work behind
   interview scheduling.

### Guardrails (conditions of the acceptance)
- **No external pilot exposure** of the scanner until Step 1 closes in writing
  (≥1 findings-review interview + ≥2 "would install an agent" confirmations,
  recorded in `validation_interviews.md`). Internal-only until then.
- **Cert order is still required** before any *public* (non-internal) binary
  distribution; internal pilots may use the unsigned-prerelease fallback (Phase 5).
- **Reversal plan if the gate fails:** if interviews return a hard "no agent," shelve
  Phases 4–6 (Go scanner / `agent-release.yml` / signing) and reallocate Month 4's
  remaining effort to Google Workspace OAuth + report polish, per the plan's
  stop/pivot branch. Keep Phases 1–3.
- **This acceptance is revisited** the moment the first agent-install interview
  lands — confirm or trigger the reversal plan then.

### Accepted by
- Engineering lead (firegiant9000) — 2026-06-13. _Team co-sign to be recorded here._

---

## Exit criteria

| Criterion | State |
|---|---|
| Both gates pass **in writing** | ⛔ pending interviews (Step 1) — **deferred under accepted risk** |
| Trust-model table ratified | ✅ frozen (Step 2) |
| Cert order placed | ⛔ pending (Step 3) — **deferred under accepted risk** |
| Migration head confirmed | ✅ 047 → 048 (Step 4) |

**Original rule:** Phase 0 exits — and Phase 1 begins — only when all four rows read
✅. **Amended 2026-06-13:** Phases 1–7 proceed now under the documented
[Risk acceptance](#risk-acceptance-issue-1--building-ahead-of-the-gate); the two ⛔
rows remain mandatory before external pilot exposure and public binary distribution.
