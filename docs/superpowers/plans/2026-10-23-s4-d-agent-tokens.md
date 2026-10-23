# S4 stage D: agent-token lifecycle (T-TOK-07, T-ENR-04, T-TOK-08) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the agent-token lifecycle end to end and close its two rule gaps (spec decision 6):
- the real `get_agent_from_token` accepts a valid token and refuses revoked, expired and past-grace tokens on both agent routes, and a replayed upload is refused (T-TOK-07, replay);
- revoking an agent revokes its whole rotation chain, and revocation never moves `revoked_at` later (T-TOK-08);
- rotation works only on active rows, so it can't extend a grace window or revive a revoked or expired enrollment (T-ENR-04).

**Architecture:**
- **Clock hook.** `agent_token._utcnow()` becomes the service's single "now" source. Every `now = now or datetime.now(UTC)` in the module becomes `now = now or _utcnow()`. The tests monkeypatch `app.services.agent_token._utcnow`. That freezes the clock that `verify`, `rotate` and `revoke` read. `verify` and `get_agent_from_token` stay unpatched.
- **Chain link.** A new nullable column, `agent_enrollments.chain_root_id`, is added by migration 051. An original row has `NULL`; every successor stores the root of its chain. "The chain of X" is every row in X's org with `id = root` or `chain_root_id = root`, where `root = X.chain_root_id or X.id`. Revoking any row in the chain revokes the whole chain with one conditional `UPDATE`, without a recursive walk.
- **Guards in the database.** Each guard is one conditional `UPDATE`:
  - rotation claims the predecessor only `WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now)`;
  - revocation sets `revoked_at = now` only `WHERE revoked_at IS NULL OR revoked_at > now`.
  
  Both first take a `SELECT … FOR NO KEY UPDATE` lock on the chain's root row, so a revoke can't miss a successor that an in-flight rotation is inserting (see Decisions). The service keeps a cheap pre-check, so the common refusal gives a clear error before any write.
- **Tests:** under real verification, in `backend/tests/authz/tenancy/`, on stage B's fixture world and no-egress stubs. Each test issues its own agents through the real service and DB. There are no `dependency_overrides` and no fake repository. The mock-based unit tests in `tests/test_agent_token.py` and `tests/test_agent_routes.py` are updated to the new rules.

**Tech Stack:** Python 3.11, FastAPI 0.133, SQLAlchemy 2 async + asyncpg, Postgres 15, Alembic, pytest 9 + pytest-asyncio, httpx `ASGITransport`, firebase-admin 6.4.0 (real verification via stage A, used here for the human management routes). Frontend: React + Vite, Vitest, eslint (`--max-warnings 0`).

**Spec:** `docs/superpowers/specs/2026-10-22-s4-authorization-assurance-design.md`: decision 6 (L125–130) in full; Anti-goals (L35–42); Constraints (L44–50); the stage D row (L147).

## Global Constraints

- **Git.**
  - Worktree `C:/dev/ht-s4-d`, branch `feat/s4-agent-tokens`, stacked on `feat/s4-roles` (#228).
  - Commit as `git -C C:/dev/ht-s4-d -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`, with the message file in the session scratchpad.
  - No Claude attribution. One shell command per Bash call.
- **Real verification only in `tests/authz/`.**
  - Human calls (rotate, revoke) go through `as_user`.
  - Agent calls use `authz_client(raw_token)` with a token issued by `agent_token.issue` / `rotate` against the real DB.
  - Never use `app.dependency_overrides`, a fake repository, or a patch on `agent_token.verify`, `get_agent_from_token` or the repository in this folder. Only `agent_token._utcnow` may be patched. Task 1's one documented exception is `SqlAgentScanNonceRepository.seen_within`, to reach the unique-constraint backstop.
- **No sleeping.** Expiry and grace are tested with the frozen clock. The one wait in the suite polls `pg_stat_activity` for a lock wait (Task 2's race test); it never sleeps a fixed time.
- **An agent refusal is exactly 401**, with `detail == "Invalid or expired agent token"` and `WWW-Authenticate: Bearer`. A 403, 404 or 500 fails the test. **Refused agent calls change nothing:** compare `snapshot_org(org_id, world.upload_dir)` before and after the agent request.
- **A rotation refusal is exactly 409** `"Only an active agent can be rotated"`, and the org snapshot is unchanged.
- **Shared, dirty test DB.**
  - Every agent a test creates is in a world org, so the org cascade removes it.
  - Every upload uses a fresh `uuid4` `scan_id` and nonce, because the nonce table's uniqueness is global.
  - Hostnames carry the org marker.
- **Existing tests are updated to the new rule, never deleted** (spec Anti-goals). A changed test keeps its name, or its rename goes in the commit body.
- **Migrations:** versioned, forward-only. Never edit 048–050. Follow the repo's pattern, which includes a `downgrade()`. `alembic check` must stay clean (gotchas, "S2 stage D"); it's in the gate.
- **Severe-finding stop.** If anything severe that S3 didn't record turns up (cross-tenant access, an auth bypass, a leaked credential): stop, leave the test uncommitted, and report to the controller in chat only. These are known and not a stop: T-TOK-07, T-ENR-04, T-TOK-08, the T-TEN-12 drift, the assessments 500, and the revoke/rotate race described in Decisions (it's part of the T-TOK-08 design, not a live bug: chain revocation doesn't exist yet).
- **Public repo.** Commit messages, notes and the PR body describe the gaps at planning level only.
- **Lint.** From `backend/`, run `ruff check app tests evals` and `ruff format app tests evals --check` (`FBT` flags keyword-only booleans; `N`, `S` and `ARG` are also on).
- **Mutation checks are owner-run.** The auto-mode classifier blocks temporary security-weakening edits. Task 4 hands Arlo the steps.

## Review Focus

1. **Two unrelated agents with the same name in one org.** Revoking one must not revoke the other: the chain follows the link, not the name. Pinned by `test_revoke_leaves_same_name_agent_alone` (Task 2).
2. **Revoking a predecessor whose grace has already ended.** The predecessor's own row changes nothing, but the live successor must still die. This is the exact T-TOK-08 scenario: an admin revokes "the agent" by the id they remember, days after a rotation. Pinned by `test_revoke_original_after_grace_revokes_successor` (Task 2).
3. **A revoke that lands while a rotation is in flight.** The new successor must not survive. Pinned by `test_revoke_waits_for_inflight_rotation` (Task 2).
4. **An idle ("stale") agent is still active**, so it must still be rotatable. A guard keyed on the derived `status` instead of `revoked_at`/`expires_at` would refuse it. The successor must be rotatable too. Pinned by `test_rotate_stale_agent_allowed` and `test_rotate_successor_allowed` (Task 3).
5. **Revoking twice.** The second call is 204, keeps the first `revoked_at`, and its audit row lists no ids. Pinned by `test_revoke_never_moves_revoked_at_later` (Task 2).

## Decisions made in this plan

- **The clock hook is `app.services.agent_token._utcnow`.** It's a module-level function returning `datetime.now(UTC)`. It's the only clock the token service reads. Patching it moves time for `verify`, `rotate` and `revoke`, and leaves their logic untouched. The upload route's replay window still reads the real clock (`inventory.py` L472), which the replay tests rely on.
- **T-ENR-04: the guard is in both the service and the repository.**
  - **Service pre-check** (`_is_active(enrollment, now)`: `revoked_at is None and (expires_at is None or expires_at > now)`). It refuses with `AgentNotActiveError` before any write, so a refused rotation writes nothing and never mints a token.
  - **Repository** `claim_for_rotation`: a conditional `UPDATE … SET revoked_at = :grace_until WHERE id = :id AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > :now) RETURNING id`. It doesn't commit. The successor's `INSERT` in `repo.create` commits the claim and the new row together. If the `INSERT` fails, the request session is discarded and the claim rolls back with it.
  - **Why both: two concurrent rotations.** Both may pass the pre-check on stale objects. Postgres row-locks the predecessor for the first `UPDATE`. The second blocks until the first commits, then re-checks its `WHERE` under READ COMMITTED, matches 0 rows, and is refused. Exactly one successor exists.
  - **Why both: rotation racing a revoke.** Whichever commits first wins. A rotation after a revoke matches 0 rows and gets 409. A revoke after a rotation revokes the whole chain, successor included (T-TOK-08).
  - **A row in its grace window counts as not active** (`revoked_at` is set). Rotating it again would mint a second successor and push its grace later, which is exactly T-ENR-04. The admin rotates the successor instead.
- **The rotation refusal is 409 `"Only an active agent can be rotated"`.** 409 because the request conflicts with the row's state. A 404 would lie (the agent exists and the admin can see it), and a 400 suggests a malformed request. The detail is the same for revoked, expired and in-grace rows; the list view already shows which one.
- **Revocation never moves `revoked_at` later.** `revoke_chain` sets `revoked_at = now` only on chain rows `WHERE revoked_at IS NULL OR revoked_at > now`. A row in grace moves earlier, to now. A row already revoked keeps its time. Repeating a revoke is a 204 no-op.
- **T-TOK-08: revocation walks the chain through a new column, not by name and not by UI.**
  - **Migration 051** adds `chain_root_id INTEGER NULL`, FK `fk_agent_enrollments_chain_root_id` → `agent_enrollments.id` `ON DELETE SET NULL`, and index `ix_agent_enrollments_chain_root_id`. Rows are never deleted one at a time (only by the org cascade), so `SET NULL` is a formality.
  - **Why a root id, not a predecessor id:** revocation is then one indexed `UPDATE` in both directions. Revoking a successor also kills a predecessor that's still in grace; the spec asks only for forward. A predecessor id would need a recursive CTE up and down.
  - **Root-row lock.** Both `claim_for_rotation` and `revoke_chain` first run `SELECT id FROM agent_enrollments WHERE id = :root FOR NO KEY UPDATE` (`.with_for_update(key_share=True)`). It's a separate statement from the `UPDATE` that follows.
    - Without it, a revoke whose `UPDATE` starts while a rotation is uncommitted blocks on the claimed row. When it resumes, it re-checks only the rows its statement snapshot already saw, so it misses the successor the rotation just inserted.
    - With it, the revoke waits for the rotation's commit, and its `UPDATE` then starts with a fresh snapshot that includes the successor.
    - **Why `NO KEY UPDATE`, not `FOR UPDATE`.** An in-flight agent upload holds a `KEY SHARE` lock on its enrollment row through the `agent_scan_nonces.agent_enrollment_id` FK until it commits. `FOR UPDATE` conflicts with that lock. A busy (or hostile) root token could then delay its own chain's revocation, and a rotation would stall uploads. `NO KEY UPDATE` doesn't conflict with `KEY SHARE`, but it still conflicts with itself, so claim/revoke and revoke/revoke still serialize.
    - Both paths lock the root first and then the target rows, so the lock order is the same and they can't deadlock. Other writers (`touch_last_used`, uploads) hold at most one row lock and wait on nothing else.
  - **The claim must commit atomically with the successor's `INSERT`.** If a later change adds a `session.rollback()` to `issue`'s collision retry, it would silently discard the claim and mint a successor without one: two active credentials. A comment in `rotate` says so, and the follow-up todo carries the rule.
  - **Residual: rotations done before migration 051 aren't linked**, and neither are rotations the old release serves during the deploy window (Render runs 051 as `preDeployCommand` while the old instances still serve traffic). Their successors have `chain_root_id = NULL`. There is no reliable way to rebuild the link: names aren't unique, and the grace setting can change. The PR's **"After deploy"** checklist lists the agents whose name occurs more than once in an org that still has a live row, so the owner can review them. The fix is to revoke each live row by its own id.
- **Replay.** The control already exists (`inventory.py::upload_agent_scan`, L469–475 fast path, L517–531 unique-constraint backstop, table `agent_scan_nonces`). Stage B's world seeds no nonce rows, and none is needed. A replay gets 409 `"Duplicate scan submission (replay detected)"`. The fast path writes nothing. The backstop path leaves one `scan_runs` row with `status = "failed"` and `error_message = "duplicate scan submission"` and nothing else; that's by design and pinned. The replay window isn't reset by a rotation, because the nonce table is global.
- **T-TOK-06 becomes TEST**, as well as the three scheduled rows. Its Notes say the inside of the grace window is the only part tested; Task 1 tests both sides of the boundary end to end, and Task 3 removes "grace is extended by re-rotating". Expected counts: 110 = **40 CONTROL / 31 TEST / 18 ACCEPTED / 21 OPEN** (plus the withdrawn T-UPL-06). Verify by counting.
- **The frontend hides Rotate for agents in grace** (`SettingsPage.tsx` L791). It already hides Rotate for revoked and expired agents; otherwise an admin clicking Rotate on a grace row now gets the 409 message.
- **`[K]` = 20:** stage C's 18, plus `POST /agents/{agent_id}/rotate` (now refuses non-active rows) and `DELETE /agents/{agent_id}` (now revokes the chain and never moves `revoked_at` later). The 2 agent routes aren't counted. Their code doesn't change; what changes is which rows the verifier finds usable, and that's credited to the two management routes.

---

### Task 1: Clock hook, T-TOK-07 end to end, and replay end to end

**Files:**
- Modify: `backend/app/services/agent_token.py` (add `_utcnow`; replace the 4 `datetime.now(UTC)` defaults at L97, L137, L181, L203)
- Create: `backend/tests/authz/tenancy/_agents.py`
- Modify: `backend/tests/authz/tenancy/conftest.py` (add the `clock` fixture)
- Test: `backend/tests/authz/tenancy/test_agent_lifecycle.py`, `backend/tests/authz/tenancy/test_agent_replay.py`
- Modify: `backend/tests/test_agent_token.py` (one new test for the hook)

**Interfaces:**
- Consumes: `world`, `as_user`, `authz_client`, `snapshot_org`, `OrgWorld` (`tenancy/conftest.py`, `_world.py`); `ROUTES` (`route_table.py`); `AsyncSessionLocal`; `SqlAgentEnrollmentRepository`; `agent_token.issue`.
- Produces:
  ```python
  # app/services/agent_token.py
  def _utcnow() -> datetime          # datetime.now(UTC); the module's only clock

  # tests/authz/tenancy/_agents.py
  AGENT_DENIED = "Invalid or expired agent token"
  REPLAY_DETAIL = "Duplicate scan submission (replay detected)"
  NOT_ACTIVE = "Only an active agent can be rotated"         # used from Task 3
  GRACE = timedelta(hours=settings.AGENT_TOKEN_ROTATION_GRACE_HOURS)
  UPLOAD = ("POST", "/api/v1/inventory/scans")
  STATUS = ("GET", "/api/v1/inventory/scans/{scan_run_id}")
  AGENT_ROUTES: tuple[tuple[str, str], ...] = (UPLOAD, STATUS)
  def frozen_now() -> datetime                               # datetime.now(UTC).replace(microsecond=0)
  def scan_payload(org: OrgWorld) -> dict                    # golden fixture tests/fixtures/agent_scan_v1.json with uuid4 scan_id, uuid4().hex nonce, host.hostname f"{org.marker}-agent-host"
  def agent_request(route: tuple[str, str], org: OrgWorld) -> Req   # UPLOAD: POST with scan_payload(org); STATUS: GET org.ids["scan_run_id"]
  ACCEPTED: dict[tuple[str, str], int] = {UPLOAD: 201, STATUS: 200}
  async def issue_agent(org: OrgWorld, *, now: datetime | None = None,
                        expires_at: datetime | None = None, name: str | None = None) -> IssuedToken
      # own AsyncSessionLocal session; name defaults to f"{org.marker}-agent-{uuid4().hex[:6]}"; created_by = org.owner
  async def load_agent(agent_id: int) -> AgentEnrollment       # fresh session, by id
  async def send(client, req: Req) -> httpx.Response
  ```
  A `clock` fixture in `tenancy/conftest.py`: `clock(monkeypatch) -> Callable[[datetime], None]`. Calling it sets `app.services.agent_token._utcnow` to return that instant.

- [ ] **Step 1: Write the tests** in `test_agent_lifecycle.py` (module `world`). Each one is parametrised over `route in AGENT_ROUTES` unless noted. Each 401 asserts the exact detail, `resp.headers["www-authenticate"] == "Bearer"`, and `snapshot_org(a)` unchanged around the agent request only.
  - `test_agent_routes_match_table` (not parametrised): `{k for k, s in ROUTES.items() if s.cls == "agent"} == set(AGENT_ROUTES)`, so a new agent route fails until it's covered.
  - `test_real_agent_verifier_in_use` (not parametrised):
    - `get_agent_from_token not in app.dependency_overrides`;
    - `agent_token.verify.__code__.co_filename` ends with `app/services/agent_token.py`, and `not hasattr(agent_token.verify, "mock")` (the gotchas' autospec lesson).
  - `test_valid_token_accepted[route]`: `issue_agent(a)` → `ACCEPTED[route]`.
  - `test_revoked_token_rejected[route]`: `clock(t0)`; issue; `as_user(a.admin)` `DELETE /api/v1/agents/{id}` → 204; the agent call at `t0` → 401.
  - `test_expired_token_rejected[route]`: `issue_agent(a, now=t0 - timedelta(days=1), expires_at=t0)`; `clock(t0)` → 401 (expiry is `<=`).
  - `test_token_accepted_just_before_expiry[route]`: same token, `clock(t0 - timedelta(seconds=1))` → `ACCEPTED[route]`.
  - `test_rotated_predecessor_accepted_inside_grace[route]`: `clock(t0)`; issue; `a.admin` `POST /api/v1/agents/{id}/rotate` → 200, keep `raw_token`; `clock(t0 + GRACE - timedelta(seconds=1))`; predecessor → accepted; successor → accepted.
  - `test_rotated_predecessor_rejected_past_grace[route]`: same setup; `clock(t0 + GRACE)`; predecessor → 401 with the snapshot check; successor → accepted.
- [ ] **Step 1b: Write the replay tests** in `test_agent_replay.py` (module `world`, real clock, no `clock` fixture):
  - `test_replayed_upload_rejected`: `p = scan_payload(a)`; POST → 201; `before = snapshot_org(a)`; POST the same `p` with the same token → 409 `REPLAY_DETAIL`; `snapshot_org(a) == before` (no new scan run, nonce or asset). The second verify is inside the 60 s `last_used_at` debounce, so the enrollment row doesn't change either.
  - `test_replay_rejected_after_rotation`: upload `p` with the token; rotate it through the route; POST `p` with the successor → 409 `REPLAY_DETAIL`; snapshot unchanged around that call.
  - `test_replay_backstop_unique_constraint`: upload `p` → 201; `monkeypatch.setattr(SqlAgentScanNonceRepository, "seen_within", <async fn returning False>)` (the only non-clock patch in the folder; it removes the fast path so the DB constraint has to answer); POST `p` again → 409 `REPLAY_DETAIL`. Every snapshot table except `scan_runs` is unchanged, and `agent_scan_nonces` still has exactly one row for `(p["scan_id"], p["nonce"])`. `scan_runs` has exactly one new row, with `status == "failed"` and `error_message == "duplicate scan submission"`.
- [ ] **Step 1c: Unit test** in `tests/test_agent_token.py`: `test_default_clock_is_utcnow_hook`. Monkeypatch `agent_token._utcnow` to a fixed instant, issue with `now=` omitted, and assert `expires_at == fixed + 365 days`. This pins the hook name the e2e tests patch.
- [ ] **Step 2: Run** `pytest tests/authz/tenancy/test_agent_lifecycle.py tests/authz/tenancy/test_agent_replay.py tests/test_agent_token.py -v` (the gate command, Task 4 Step 5, with these targets). Expected before Step 3: the `clock`-dependent tests fail because patching `_utcnow` has no effect (no such attribute: `AttributeError` from `monkeypatch.setattr`, which is `raising=True`), and so does `test_default_clock_is_utcnow_hook`. The rest pass: T-TOK-07 closes with tests alone. A failure of a non-clock lifecycle or replay test goes to the controller; it could be a severe finding.
- [ ] **Step 3: Implement `_utcnow`** and route every default through it. Nothing else in the service changes in this task.
- [ ] **Step 4: Run** the same targets, then `pytest tests/authz -q`. Expected: all pass. Record the added runtime.
- [ ] **Step 5: Commit** `test(agents): end-to-end token lifecycle and replay tests on both agent routes (T-TOK-07)`. Body: real verifier, injectable service clock, boundaries tested on both sides, replay fast path and unique-constraint backstop.

### Task 2: T-TOK-08 — revocation covers the rotation chain and never moves `revoked_at` later

**Files:**
- Create: `backend/app/db/versions/051_add_agent_enrollment_chain_root.py` (revision `"051"`, down_revision `"050"`)
- Modify: `backend/app/db/agent_enrollment.py` (add `chain_root_id`; docstring: one line on the chain)
- Modify: `backend/app/repositories/agent_enrollments.py` (`create` gains `chain_root_id`; add `_lock_chain_root`, `revoke_chain`)
- Modify: `backend/app/services/agent_token.py` (`issue` gains `chain_root_id`; `rotate` passes it; `revoke` uses `revoke_chain`)
- Modify: `backend/app/api/routes/v1/agents.py::revoke_agent` (L125: audit payload gains `revoked_ids`; docstring)
- Test: `backend/tests/authz/tenancy/test_agent_chain.py`
- Modify: `backend/tests/test_agent_token.py`, `backend/tests/test_agent_routes.py` (see Task 5)

**Interfaces:**
- Consumes: Task 1's `_agents.py` helpers and `clock`.
- Produces:
  ```python
  # app/db/agent_enrollment.py
  chain_root_id: Mapped[int | None] = mapped_column(
      ForeignKey("agent_enrollments.id", ondelete="SET NULL", name="fk_agent_enrollments_chain_root_id"),
      nullable=True, index=True)     # index name must come out as ix_agent_enrollments_chain_root_id

  # app/repositories/agent_enrollments.py
  async def create(self, org_id, *, name, token_hash, token_prefix, scopes, created_by_user_id,
                   expires_at, chain_root_id: int | None = None) -> AgentEnrollment
  async def _lock_chain_root(self, root_id: int) -> None        # SELECT id … WHERE id = :root FOR NO KEY UPDATE (with_for_update(key_share=True))
  async def revoke_chain(self, enrollment: AgentEnrollment, *, when: datetime) -> list[int]
      # root = enrollment.chain_root_id or enrollment.id; _lock_chain_root(root);
      # UPDATE … SET revoked_at = :when WHERE org_id = :org AND (id = :root OR chain_root_id = :root)
      #   AND (revoked_at IS NULL OR revoked_at > :when) RETURNING id
      # synchronize_session=False; commit; refresh(enrollment); return sorted ids changed

  # app/services/agent_token.py
  def chain_root(enrollment: AgentEnrollment) -> int            # enrollment.chain_root_id or enrollment.id
  async def issue(..., chain_root_id: int | None = None) -> IssuedToken
  async def revoke(repo, enrollment, *, now: datetime | None = None) -> list[int]   # ids whose revoked_at changed
  ```
  `rotate` passes `chain_root_id=chain_root(enrollment)` to `issue`. `revoke_agent` keeps the 204 and the 404. Its audit payload becomes `{"agent_id": agent_id, "revoked_ids": <list>}`. `set_revoked_at` stays until Task 3 (`rotate` still uses it).

- [ ] **Step 1: Write the failing tests** in `test_agent_chain.py` (module `world`). "Rotate" and "revoke" go through `as_user(a.admin)` on the real routes; the agent checks use `authz_client(token)` on `STATUS` (the 401 contract on both routes is Task 1's). Each 401 asserts `AGENT_DENIED` and an unchanged snapshot around the agent call.
  - `test_revoke_original_revokes_successor[route]` (parametrised over `AGENT_ROUTES`): `clock(t0)`; issue X; rotate X → successor S; revoke X → 204; S on `route` → 401; X → 401. The newest `agent.revoke` `AuditLog` row for A has `payload["revoked_ids"] == sorted([X.id, S.id])`.
  - `test_revoke_original_after_grace_revokes_successor`: rotate at `t0`; `clock(t0 + GRACE + timedelta(hours=1))`; revoke X → 204; S → 401 (Review Focus 2). `load_agent(X)` still has `revoked_at == t0 + GRACE`: it's earlier than now, so it isn't moved.
  - `test_revoke_successor_revokes_predecessor_in_grace`: rotate at `t0`; `clock(t0 + timedelta(hours=1))`; revoke S; X → 401; `load_agent(X).revoked_at == t0 + timedelta(hours=1)` (moved earlier).
  - `test_revoke_covers_two_rotations`: X → S1 → S2 (rotate S1); revoke X → S2 → 401; `load_agent(S2).chain_root_id == X.id`.
  - `test_revoke_leaves_same_name_agent_alone`: `issue_agent(a, name=n)` twice (two separate enrollments, so two chains); revoke the first; the second → `ACCEPTED[STATUS]` (Review Focus 1).
  - `test_revoke_never_moves_revoked_at_later`: `clock(t0)`; revoke X → 204; `clock(t0 + timedelta(hours=1))`; revoke X again → 204; `load_agent(X).revoked_at == t0`; that audit row has `revoked_ids == []` (Review Focus 5).
  - `test_revoke_waits_for_inflight_rotation` (service level, real DB, Review Focus 3). It stands in for a rotation that holds the chain lock and hasn't committed yet. Task 3 adds the version that drives the real claim.
    1. Issue X. In session 1, read `p1 = SELECT pg_backend_pid()`, then call `repo1._lock_chain_root(X.id)` and don't commit.
    2. In session 2, run `SET LOCAL lock_timeout = '10s'`, read `p2 = pg_backend_pid()`, load X as `x2`, and start `task = asyncio.create_task(agent_token.revoke(repo2, x2))`.
    3. `await wait_until_blocked(p2, blocker=p1)` (helper below). On timeout it fails with "revoke did not wait for the chain lock".
    4. In session 1, run `agent_token.issue(repo1, org_id=a, …, chain_root_id=X.id)`, which commits and releases the lock.
    5. `ids = await asyncio.wait_for(task, 10)`. `ids` includes the new successor's id, and the successor's token → 401.
    6. The whole body is in `try/finally`. The `finally` cancels the task if it's still pending, then rolls back and closes sessions 1 and 2, so a failure can't leave a row lock that hangs `drop_world`'s org delete.

  Add to `_agents.py`: `async def wait_until_blocked(pid: int, *, blocker: int, timeout: float = 5.0) -> None`. It polls from its own session, at 50 ms intervals, `SELECT 1 FROM pg_stat_activity WHERE pid = :pid AND wait_event_type = 'Lock' AND :blocker = ANY(pg_blocking_pids(:pid))`, and raises `AssertionError` at the deadline. Scoping the poll to the two pids keeps another backend on the shared DB from satisfying it.
- [ ] **Step 1b: Unit tests** in `tests/test_agent_token.py`, with the fake repo extended per Task 5:
  - `test_rotate_links_successor_to_chain_root`: S1 and S2 both have `chain_root_id == X.id`.
  - `test_revoke_returns_changed_ids`: `[X.id, S.id]`, then `[]` on a repeat.
- [ ] **Step 2: Run** `pytest tests/authz/tenancy/test_agent_chain.py tests/test_agent_token.py -v`. Expected failures, all part of the known T-TOK-08 gap:
  - the chain tests (the successor survives, and `chain_root_id` doesn't exist);
  - `test_revoke_never_moves_revoked_at_later`, on the time;
  - the race test (`_lock_chain_root` doesn't exist).
- [ ] **Step 3: Implement** per Interfaces: the migration (`add_column`, `create_foreign_key("fk_agent_enrollments_chain_root_id", "agent_enrollments", "agent_enrollments", ["chain_root_id"], ["id"], ondelete="SET NULL")`, `create_index("ix_agent_enrollments_chain_root_id", …)`; `downgrade` reverses them in order), the model, the repo and the service. Update the `revoke` docstring: "Revoke the whole rotation chain immediately; never moves an earlier `revoked_at` later."
- [ ] **Step 4: Migrate and check drift**, each its own call in the gate container: `alembic -c app/db/alembic.ini upgrade head`, then `alembic -c app/db/alembic.ini check` → "No new upgrade operations detected."
- [ ] **Step 5: Run** the Step 2 targets, then `pytest tests/authz tests/test_agent_token.py tests/test_agent_routes.py -q`. Expected: all pass.
- [ ] **Step 6: Commit** `fix(agents): revoking an agent revokes its rotation chain and never extends a revocation (T-TOK-08)`. Body: the new column and migration 051, the root-row lock, and the pre-migration residual at planning level.

### Task 3: T-ENR-04 — rotation acts only on active rows

**Files:**
- Modify: `backend/app/repositories/agent_enrollments.py` (add `claim_for_rotation`; delete `set_revoked_at`, now unused)
- Modify: `backend/app/services/agent_token.py` (`AgentNotActiveError`, `_is_active`, `rotate`)
- Modify: `backend/app/api/routes/v1/agents.py::rotate_agent` (L97: catch, 409; docstring)
- Modify: `backend/tests/authz/route_table.py` (notes on the rotate and revoke entries, L440–441)
- Modify: `frontend/src/pages/SettingsPage.tsx` (L791), `frontend/src/pages/__tests__/SettingsPage.members.test.tsx`
- Test: `backend/tests/authz/tenancy/test_agent_rotation.py`
- Modify: `backend/tests/test_agent_token.py`, `backend/tests/test_agent_routes.py` (see Task 5)

**Interfaces:**
- Consumes: Task 2's `chain_root`, `_lock_chain_root`, `issue(..., chain_root_id=)`.
- Produces:
  ```python
  # app/repositories/agent_enrollments.py
  async def claim_for_rotation(self, enrollment: AgentEnrollment, *, grace_until: datetime, now: datetime) -> bool
      # _lock_chain_root(root); UPDATE … SET revoked_at = :grace_until WHERE id = :id AND revoked_at IS NULL
      #   AND (expires_at IS NULL OR expires_at > :now) RETURNING id; synchronize_session=False; NO commit.
      # On success also sets enrollment.revoked_at = grace_until in memory. Returns whether a row matched.

  # app/services/agent_token.py
  class AgentNotActiveError(Exception): ...
  def _is_active(enrollment: AgentEnrollment, now: datetime) -> bool   # revoked_at is None and (expires_at is None or > now), via _as_aware
  async def rotate(repo, enrollment, *, created_by_user_id, now=None) -> IssuedToken
      # now = now or _utcnow(); not _is_active → raise; not await repo.claim_for_rotation(...) → raise;
      # then issue(..., chain_root_id=chain_root(enrollment), now=now), whose create() commits claim + successor together

  # app/api/routes/v1/agents.py
  NOT_ACTIVE_DETAIL = "Only an active agent can be rotated"
  # rotate_agent: except agent_token.AgentNotActiveError → HTTPException(409, NOT_ACTIVE_DETAIL), before any audit
  ```
  The order inside `rotate` matters: claim first, then issue. The reverse would commit a successor before the claim is known to have won. A comment in `rotate` states the rule: the claim must commit in the same transaction as the successor's `INSERT`, so nothing may roll back between them (see Decisions).

- [ ] **Step 1: Write the failing tests** in `test_agent_rotation.py` (module `world`). Each 409 asserts `NOT_ACTIVE`, an unchanged `snapshot_org(a)` around the refused call, and no new `agent_enrollments` row in A.
  - `test_rotate_refused_when_revoked`: issue; revoke through the route; rotate → 409.
  - `test_rotate_refused_when_expired`: `issue_agent(a, now=t0 - timedelta(days=1), expires_at=t0)`; `clock(t0)`; rotate → 409.
  - `test_rotate_refused_during_grace`: `clock(t0)`; rotate X → 200; rotate X again → 409; `load_agent(X).revoked_at == t0 + GRACE` (not extended); exactly one row has `chain_root_id == X.id`.
  - `test_rotate_successor_allowed`: rotate X → S1; rotate S1 → 200; the new row's `chain_root_id == X.id` (Review Focus 4).
  - `test_rotate_stale_agent_allowed`: issue; set `last_used_at = t0 - timedelta(days=45)` in a direct session (status "stale"); `clock(t0)`; rotate → 200 (Review Focus 4).
  - `test_stale_object_rotation_refused_by_database` (service level, real DB): load X in session 1 and session 2; `agent_token.rotate(repo1, x1, …)` succeeds; `agent_token.rotate(repo2, x2, …)` raises `AgentNotActiveError`. The pre-check passed on the stale `x2`, so only the conditional `UPDATE` refused it. Exactly one successor; `load_agent(X).revoked_at` is the first rotation's grace.
  - `test_rotation_after_revoke_refused_by_database`: load X in session 1; `agent_token.revoke(repo2, x2)` in session 2; `agent_token.rotate(repo1, x1, …)` raises `AgentNotActiveError`; no successor; `revoked_at` is the revoke's time.
  - `test_concurrent_rotations_one_wins`: load X in two sessions; `asyncio.gather(rotate(repo1, x1), rotate(repo2, x2), return_exceptions=True)` gives exactly one `IssuedToken` and one `AgentNotActiveError`, with one successor row.
  - `test_revoke_mid_chain_waits_for_inflight_claim` (Review Focus 3, with the real claim). It covers what Task 2's race test can't: the root lock inside `claim_for_rotation`, and `revoke_chain` locking the root rather than the row it was given.
    1. Set up the chain X → S1 → S2 and move `clock` past X's grace.
    2. In session 1 (`p1`), load S2 and call the real `repo1.claim_for_rotation(s2, grace_until=…, now=…)`. Stop before `issue`, without committing.
    3. In session 2 (`p2`, `SET LOCAL lock_timeout = '10s'`), load S1 and start `task = create_task(agent_token.revoke(repo2, s1))`.
    4. `await wait_until_blocked(p2, blocker=p1)`.
    5. In session 1, `issue(repo1, …, chain_root_id=X.id)` → S3, committed.
    6. `ids = await asyncio.wait_for(task, 10)`. `ids` contains S3's id, and S3's token → 401.
    7. Use the same `try/finally` cleanup as Task 2's race test.
- [ ] **Step 1b: Unit tests** in `tests/test_agent_token.py`:
  - `test_rotate_refuses_revoked`, `test_rotate_refuses_expired` and `test_rotate_refuses_in_grace`: each raises `AgentNotActiveError`, no new fake row, `revoked_at` unchanged;
  - `test_rotate_refuses_when_claim_lost`: the fake's `claim_for_rotation` returns `False` → raises, no new row.
  
  In `tests/test_agent_routes.py`: `test_rotate_inactive_409`: `agent_token.rotate` patched to raise `AgentNotActiveError` → 409 with `NOT_ACTIVE_DETAIL`, and `_audit` not called.
- [ ] **Step 2: Run** the new files. Expected: the refusal tests fail (rotation succeeds today), and so do the stale-object and concurrent tests (two successors). The mid-chain race test fails because `claim_for_rotation` doesn't exist yet. This is the known T-ENR-04 gap. `test_rotate_successor_allowed` and `test_rotate_stale_agent_allowed` pass.
- [ ] **Step 3: Implement** per Interfaces. `route_table.py` notes:
  - rotate: `"rotates active agents only (T-ENR-04)"`;
  - revoke: `"revokes the whole rotation chain (T-TOK-08)"`.
  
  `min_role` and `cls` are unchanged.
- [ ] **Step 4: Frontend.** In `SettingsPage.tsx`, show Rotate only when `a.status !== "revoked" && a.status !== "expired" && a.status !== "grace"`. Update the help text near L662–664: "Rotate to replace a token (the old one keeps working for 24 hours; rotate the new one, not the old); revoke to cut off the agent and every token rotated from it." Add to `SettingsPage.members.test.tsx`:
  - `hides Rotate for an agent in grace`: `mockListAgents` returns one agent with `status: "grace"`; no button titled "Rotate token"; the "Revoke agent" button is present;
  - `shows Rotate for an active agent`.
- [ ] **Step 5: Run** `pytest tests/authz tests/test_agent_token.py tests/test_agent_routes.py -v`, then the full `pytest tests/`. Then, from `frontend/`: `npm run lint`, `npm test`, `npm run build`. Expected: all pass, including stage B/C's rotate cases (each allowed rotate there runs on a `fresh_world`'s active seeded agent, so it stays 200).
- [ ] **Step 6: Commit** `fix(agents): rotate only active agents, refusing revoked, expired and in-grace rows (T-ENR-04)`, and a separate `feat(frontend): hide Rotate for agents in their grace window`.

### Task 4: Threat model, docs, gate, PR

**Files:**
- Modify: `docs/security/threat_model.md`: T-ENR-04 (L116), T-UPL-01 (L124, Notes), T-TOK-06 (L143), T-TOK-07 (L144), T-TOK-08 (L145), T-RPL-01 (L152, add the e2e test id), Findings item 4 (L291), OPEN RISK S4 row (L307)
- Modify: `docs/security/agent_enrollment.md` (L27, L71: rotation of active agents only; revocation covers the chain)
- Modify: `docs/manual_test_month4.md` (L68 and L90: add "rotating an agent in grace is refused (409)" and "revoking the old id also kills the new token")
- Modify: `README.md:162`; `docs/PRODUCT_VIABILITY_ROADMAP.md:277`

- [ ] **Step 1: Rows.**
  - **T-TOK-07 → TEST.** Evidence:
    - `` `backend/tests/authz/tenancy/test_agent_lifecycle.py::test_rotated_predecessor_rejected_past_grace` ``;
    - `` `backend/tests/authz/tenancy/test_agent_lifecycle.py::test_revoked_token_rejected` ``.
    
    Notes: `real-verification: no dependency override and no fake repository; on both agent routes a valid token is accepted and a revoked, expired or past-grace token is refused with 401 and nothing written; boundaries are tested on both sides with an injected service clock.` The marker isn't required for TOK, but it's added for consistency with AUTH/TEN.
  - **T-ENR-04 → TEST.** Evidence:
    - `` `backend/tests/authz/tenancy/test_agent_rotation.py::test_rotate_refused_during_grace` ``;
    - `` `backend/tests/authz/tenancy/test_agent_rotation.py::test_stale_object_rotation_refused_by_database` ``.
    
    Notes: "Rotation claims the old row with a conditional update, so revoked, expired and in-grace rows are refused (409) even under concurrent requests; revocation never moves `revoked_at` later (`test_agent_chain.py::test_revoke_never_moves_revoked_at_later`). Fixed in S4-D."
  - **T-TOK-08 → TEST.** Evidence: `` `backend/tests/authz/tenancy/test_agent_chain.py::test_revoke_original_revokes_successor` ``. Notes: "Rows carry their chain root; revoking any row revokes the chain, and a revoke waits for an in-flight rotation. Fixed in S4-D. Residual: rotations made before the fix aren't linked (see the PR's deploy checklist)."
  - **T-TOK-06 → TEST.** Evidence: `` `backend/tests/authz/tenancy/test_agent_lifecycle.py::test_rotated_predecessor_rejected_past_grace` ``, `` `backend/tests/authz/tenancy/test_agent_lifecycle.py::test_rotated_predecessor_accepted_inside_grace` ``. Notes: "Grace is 24h from the single permitted rotation; a row in grace can't be rotated again (T-ENR-04)."
  - T-UPL-01 Notes: append "; tested end to end with the real dependency in `tests/authz/tenancy/test_agent_lifecycle.py`".
  - T-RPL-01 Evidence: add `` `backend/tests/authz/tenancy/test_agent_replay.py::test_replayed_upload_rejected` ``.
  - Findings item 4: append " Fixed in S4-D."
- [ ] **Step 2: OPEN RISK S4 row.** Remove T-ENR-04, T-TOK-07 and T-TOK-08, leaving 5: T-PLAT-06, T-UPL-09, T-DOM-09, T-PLAT-01, T-PLAT-09.
- [ ] **Step 3: Recount** by Class. Expected 110: 40 CONTROL / 31 TEST / 18 ACCEPTED / 21 OPEN (T-UPL-06 is withdrawn and outside the 110). Count, and use the real numbers if they differ.
  - Update `README.md:162`, and check that `docs/README.md` still says 110.
  - In the roadmap at L277, append `Stage D (agent-token lifecycle: end-to-end token tests on both agent routes, chain revocation, active-only rotation) — PR #TBD.`
- [ ] **Step 4: Commit** `docs(threat-model): T-TOK-07, T-ENR-04 and T-TOK-08 closed by S4 agent-token tests`.
- [ ] **Step 5: Gate**, each its own call. Reuse `ht-s4-net`, `ht-s4-pg` and `ht-s4-venv`; check them with `docker ps -a --filter name=ht-s4-pg` and start the container if it's stopped. Before the run, delete the leftover `users` row with `email = 'testuser@example.com'`, using `docker exec ht-s4-pg psql -U postgres -d cyber_threat_test_db -c "DELETE FROM users WHERE email = 'testuser@example.com'"`. Don't drop or recreate the database.
  - Backend:
    ```
    MSYS_NO_PATHCONV=1 docker run --rm --network ht-s4-net -v C:/dev/ht-s4-d/backend:/app -v ht-s4-venv:/venv -v ht-pipcache:/root/.cache/pip -w /app -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@ht-s4-pg:5432/cyber_threat_test_db -e APP_ENV=testing python:3.11-slim sh -c "python -m venv /venv && /venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt && /venv/bin/ruff check app tests evals && /venv/bin/ruff format app tests evals --check && /venv/bin/alembic -c app/db/alembic.ini upgrade head && /venv/bin/alembic -c app/db/alembic.ini check && /venv/bin/pytest tests/ -q"
    ```
    Expected: ruff clean; `alembic check` clean; pytest 2069 + the new tests, 0 failed, 1 skipped.
  - Frontend: `npm run lint`, `npm test`, `npm run build` in `C:/dev/ht-s4-d/frontend` (477 + 2 tests).
  - `python .github/scripts/check_threat_model.py docs/security/threat_model.md`: exit 0.
  - `python -m unittest discover -s .github/scripts`: OK (65).
- [ ] **Step 6: Owner-run mutation checks (hand to Arlo, don't run).** For each: make the edit, run the named test with the gate command, confirm it fails, revert, and confirm `git -C C:/dev/ht-s4-d diff --stat backend/app` is empty.
  - In `claim_for_rotation`, drop `revoked_at IS NULL` from the `WHERE` → `test_stale_object_rotation_refused_by_database` fails.
  - In `rotate`, delete the `_is_active` pre-check → `test_rotate_refused_during_grace` still passes (the database guard holds), and `tests/test_agent_token.py::test_rotate_refuses_in_grace` fails. That shows both layers are tested.
  - In `revoke_chain`, replace the chain condition with `id = :id` → `test_revoke_original_revokes_successor` fails.
  - In `revoke_chain`, delete the `_lock_chain_root` call → `test_revoke_waits_for_inflight_rotation` fails.
  - In `revoke_chain`, lock `enrollment.id` instead of the chain root → `test_revoke_mid_chain_waits_for_inflight_claim` fails.
  - In `claim_for_rotation`, delete the `_lock_chain_root` call → `test_revoke_mid_chain_waits_for_inflight_claim` fails.
  - In `revoke_chain`, drop `(revoked_at IS NULL OR revoked_at > :when)` → `test_revoke_never_moves_revoked_at_later` fails.
  - In `agent_token.verify`, delete the `revoked_at` check (L152–153) → `test_revoked_token_rejected[...]` fails on both routes.
- [ ] **Step 7: The controller pushes and opens the draft PR.**
  - Target `main`, title `S4-D: agent-token lifecycle (revocation, rotation, expiry end to end)`. Verify `baseRefName == main`. Don't mark it ready.
  - Body:
    - start with `> Stacked on #228`;
    - the decisions above at planning level: the clock hook, the 409 refusal, chain revocation via `chain_root_id`, the root-row lock and why, revocation never moving later, and the frontend change;
    - migration 051;
    - the replay behaviour, including the backstop's failed scan run;
    - the threat-model counts, and `[K]` = 20 with its reasoning;
    - an unchecked "Mutation check (owner)" section with Step 6's steps;
    - an unchecked **"After deploy (owner, once the new release is live)"** checklist:
      - confirm that migration 051 ran (Render's `preDeployCommand` runs `alembic upgrade head`);
      - list the agents whose name occurs more than once in an org that still has a live row. That covers pre-fix chains and any rotation the old release served during the deploy window. Query: `SELECT org_id, name, count(*) FROM agent_enrollments GROUP BY 1, 2 HAVING count(*) > 1 AND bool_or(revoked_at IS NULL OR revoked_at > now())`. Those chains aren't linked, so revoking the old id won't reach the successor; revoke any compromised live row by its own id;
      - agents that were in grace at deploy time can't be rotated again; rotate their successor instead.

    Wording stays at planning level (public repo).
- [ ] **Step 8: Record follow-ups.** The controller writes them to Obsidian `todos.md` under "S4 stage D". Candidates:
  - **`issue`'s prefix-collision retry** catches `IntegrityError` without a rollback, so a real collision would surface as a 500 on the next attempt. That fails safe, and it's pre-existing and vanishingly unlikely with a 32-bit prefix and a pre-check. **A fix must not add a plain `session.rollback()`:** that would discard the rotation claim and mint an unclaimed successor (two active credentials). Wrap only the `INSERT` in `session.begin_nested()`, or re-run `claim_for_rotation` before retrying.
  - **The successor's expiry** restarts at 365 days on every rotation, so a chain can live indefinitely through rotations. That's intended (rotation is renewal), but it isn't documented.
  - **Agent `scopes`** are still unenforced (T-ENR-06 stays ACCEPTED).

### Task 5: Existing tests the new rules change (reference list; each item is done in the task named)

Not a separate commit: Tasks 1–3 each update their own items. Surveyed 2026-10-23 at `7235f1c`.

- **`tests/test_agent_token.py`** (fake repository, service unit tests):
  - `FakeAgentEnrollmentRepo` (L20):
    - Task 2: `create` gains `chain_root_id`; add `revoke_chain` with the same semantics as the SQL (rows in the same org with `id == root` or `chain_root_id == root`, and `revoked_at is None or revoked_at > when`; set `when`; return sorted ids).
    - Task 3: add `claim_for_rotation` (the same predicate as the SQL; sets `revoked_at`; returns bool) and remove `set_revoked_at` (L59).
  - `test_revoke_sets_revoked_at_to_now` (L250), Task 2: keeps its name and its assertion that `issued.enrollment.revoked_at == now`. The return value is now a list, so it also asserts `== [issued.enrollment.id]`.
  - `test_verify_rejects_revoked_token` (L194): unchanged (it ignores the return value).
  - `test_rotate_issues_new_token_and_grace_keeps_old_valid` (L221): passes unchanged. Task 2 adds `assert rotated.enrollment.chain_root_id == original.enrollment.id`.
  - New in this stage: `test_default_clock_is_utcnow_hook` (Task 1); `test_rotate_links_successor_to_chain_root`, `test_revoke_returns_changed_ids` (Task 2); `test_rotate_refuses_revoked`, `test_rotate_refuses_expired`, `test_rotate_refuses_in_grace`, `test_rotate_refuses_when_claim_lost` (Task 3).
- **`tests/test_agent_routes.py`** (overrides the role check, the org, the repo and the session):
  - `test_revoke_returns_204` (L142), Task 2: `revoke_mock` returns `[1]` instead of an enrollment, because the route now puts the return value in the audit payload. Keep `assert_awaited_once`.
  - `test_rotate_issues_new_token` (L125): unchanged (`rotate` is mocked).
  - `test_rotate_unknown_or_cross_org_id_404` (L159) and `test_revoke_unknown_or_cross_org_id_404` (L174): unchanged.
  - New: `test_rotate_inactive_409` (Task 3).
- **`tests/test_agent_scan_routes.py`** (overrides `get_agent_from_token`): unchanged. Its 401 test (L257) stays a wiring test, and the real 401 is now in `tests/authz`. Its replay tests (L221, L235) stay as handler tests.
- **`tests/authz/`:** the stage B/C sweeps call rotate and revoke only as allowed calls on a `fresh_world` (one call per world) or as denied calls. `test_cross_tenant.py::test_agent_token_scoped_to_its_org` issues an active token. Expected unchanged. A failure there means a test-ordering assumption broke; it goes to the controller, and isn't fixed by loosening the case.
- **`_world.py`:** no change. `agent_token.issue`'s new keyword has a default, and `drop_world`'s org cascade removes the chain rows.
