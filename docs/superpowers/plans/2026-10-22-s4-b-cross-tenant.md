# S4 stage B: fixture world, cross-tenant sweep, T-TEN-10 fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Under real token verification, prove that no organization-scoped route lets org B (or a user with no org) read or change org A's data. Pin the global-admin boundary and the split-user drift per route. Bind analytics events to the caller's org (T-TEN-10).

**Architecture:** Stage A's `backend/tests/authz/` harness is extended with a `tenancy/` subpackage:
- a seeded **world**: orgs A, B and C, with users in both role stores and one row of every resource kind per org;
- a **case table**: one request builder per organization-scoped route, plus that route's pinned outcomes. A coverage test ties the case table to `route_table.ROUTES`.
- four parametrised test modules that run the cases as different callers:
  - the positive control;
  - the cross-tenant denial;
  - the global admin;
  - the split user.

  Denied calls compare a snapshot of all of org A's rows before and after.

**Tech Stack:** Python 3.11, FastAPI 0.133, SQLAlchemy async + Postgres 15, pytest 9 + pytest-asyncio (`asyncio_mode = auto`, session loop for fixtures and tests), httpx `ASGITransport`, firebase-admin 6.4.0 (real verification via stage A).

**Spec:** `docs/superpowers/specs/2026-10-22-s4-authorization-assurance-design.md`: decision 4 in full; decisions 1–3; Anti-goals; Constraints; stage B row.

## Global Constraints

- **Git.**
  - Worktree `C:/dev/ht-s4-b`, branch `feat/s4-cross-tenant`, stacked on `feat/s4-authz-suite` (#226).
  - Commit as `git -C C:/dev/ht-s4-b -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`, with the message file in the session scratchpad.
  - No Claude attribution. One shell command per Bash call.
- **Every test in the suite runs under real verification.** The stage-A conftest is unchanged. Use real minted tokens only: never the global `client` fixture and never a `dependency_overrides[get_current_user]`.
- **Accepting 500 as denial is a failure.** A denied call returns exactly 403 or 404. A 401, 422, 429, 500 or 503 on a denial case fails the test.
- **Write tests assert org A unchanged.** Every denial case (reads included, because some GETs write caches) compares `snapshot_org(A)` before and after. In this plan, `snapshot_org(a)` is shorthand for `snapshot_org(world.a.org_id, world.upload_dir)`.
- **Severe-finding stop.**
  - **What triggers it:** any of the following that S3 didn't record:
    - a B caller or the no-org user gets `allowed` on an A target;
    - the split user reaches org C;
    - a denied body contains A's marker or emails.
  - **What to do:** stop. Leave the failing test uncommitted, report to the controller in chat only, and write nothing about it in code comments, commits or the PR.
  - **Known, not a stop:**
    - T-TEN-10: the analytics route accepts a client-supplied org. It is fixed in Task 2.
    - T-TEN-05.
    - The split user reaching A or B: the T-TEN-12 drift.
- **Public repo.** Notes, commit messages and the PR body describe gaps at planning level. Include no request recipes for a live weakness.
- **Lint.** From `backend/`, run `ruff check app tests evals` and `ruff format app tests evals --check`. The rules include `FBT` (flags are keyword-only), `N`, `S` and `ARG`.
- **The shared test DB is dirty:** there's no cleanup between tests, and other files leave rows behind.
  - Every seeded string carries the world's per-run marker.
  - Every query filters by the world's own ids.
  - The world deletes what it created on teardown, and nothing else.
- **There is no org-level `viewer` role.** Org roles are `member`, `admin` and `owner` (`dependencies.py::_ORG_ROLE_LEVELS`), so the world has no viewer, contrary to the spec's "(if the role exists)".

## Review Focus

1. **A denial for the wrong reason.** Body or file validation runs before the handler-body `check_org_access` on about 14 routes. The M365 routes return 503 or 500 before the org check when the flag or config is missing. A malformed builder would therefore produce a 422 or 503 that looks like a denial. Pinned by Task 3's `test_target_owner_allowed`: every builder succeeds for its own org's owner. Also pinned by the exact `{403, 404}` assertion in Task 4.
2. **The module-scoped world is mutated by an allowed call**, which would hide a later leak or break a later case.
   - The denial sweep uses the module-scoped `world`. Any change it makes fails that test's snapshot check.
   - Every test that expects an allowed call (positive control, global admin, split user) uses a function-scoped `fresh_world`.
   - Pinned by `test_world_snapshot_stable` (Task 1): two snapshots with no call in between are equal. This is the snapshot's own control.
3. **Egress during allowed calls.** Domain checks, crt.sh/HIBP/Shodan/OTX, Gemini and Microsoft Graph must never be reached from tests. The autouse `_no_egress` fixture stubs each import site. Pinned by `test_no_egress_stubs_installed` (Task 1), which asserts that each patched name is the stub.
4. **A leak hidden by a role gate.** A B member is refused by the role check before tenancy is ever tested. So each case pins `denial` for B's **owner**: the most privileged B role, which passes every role gate. The split user is an admin in both stores, for the same reason. Pinned in Task 4: the B owner's status must equal `case.denial` exactly.
5. **A route added later with no case.** Pinned by `test_every_org_scoped_route_has_a_case` (Task 3), which fails on a missing or stale case. This is spec decision 4's "parametrised from the table".

## Decisions made in this plan

- **T-TEN-10 rule.** The event's org is always `current_user.org_id`, taken from the legacy store, the same one `get_current_org` reads.
  - If the body's `org_id` is present and differs, the route returns **403** `"Access denied"` and writes nothing. A visible refusal beats silently rewriting the field, and every frontend caller already sends its own `useAuth().orgId` or `null`.
  - If the body's `org_id` is absent or `null`, the event is stored with the caller's org, which may be `None` for a user who hasn't onboarded yet.
  - There is no global-admin bypass: an event records the caller's own activity.
  - The table entry becomes `org_from="caller"`, `min_role=None`. This is 1 route towards `[K]`.
- **The 403 vs 404 record is pinned in the case table** (`Case.denial`, for B's owner) rather than written to a file. The PR table is generated from `_cases.py`. The expected pattern:
  - a route that names the org (path, query or body) returns **403** from the org check;
  - a route that takes the org from the caller and names one of A's resource ids returns **404**, because the lookup is scoped to the caller's org, so A's row doesn't exist for B;
  - `PUT`/`DELETE /assessments/{id}` returns 403 for A's existing id. Their unscoped lookup returns 404 for an unknown id first (T-TEN-11), so they leak existence of random UUIDs only.
- **Stage-A deferred minors.**
  - **Fixed here:**
    - the Rules-line wording (threat model L15);
    - the `route_table.py` docstring, which now says that the org-check and `min_role` behaviour is proven by `tenancy/`, not by `check_table`. That closes the "public only means no auth dependency" minor for org-scoped routes.
  - **Left for `dual-review`** (unchanged by stage B; no stage-B route changes):
    - the `== 128` count pin;
    - HEAD/OPTIONS-only Starlette routes;
    - the terminal-summary wording.

---

### Task 1: Fixture world and tenancy fixtures

**Files:**
- Create: `backend/tests/authz/tenancy/__init__.py` (empty)
- Create: `backend/tests/authz/tenancy/_world.py`
- Create: `backend/tests/authz/tenancy/conftest.py`
- Test: `backend/tests/authz/tenancy/test_world.py`

**Interfaces:**
- Consumes: `mint_id_token`, `SigningKey` (`tests/authz/_issuer.py`); fixtures `accounts`, `signing_key`, `authz_client` (`tests/authz/conftest.py`); `AsyncSessionLocal` (`app/db/engine.py`); `agent_token.issue` with `SqlAgentEnrollmentRepository`.
- Produces (`_world.py`):
  ```python
  @dataclass(frozen=True)
  class WorldUser:
      key: str            # "a_owner", "b_member", "global_admin", "no_org", "split", ...
      uid: str            # firebase uid, f"authz-{marker}-{key}"
      email: str
      user_id: int

  @dataclass(frozen=True)
  class OrgWorld:
      name: str           # "A" | "B" | "C"
      org_id: int
      marker: str         # f"ht{name.lower()}{hex8}", ALL lowercase (domains are lowercased); in every seeded string field
      owner: WorldUser | None
      admin: WorldUser | None
      member: WorldUser | None
      ids: dict[str, int | str]   # keys below; the first row of each kind
      ids_all: dict[str, list[int]]  # "domains", "vendors", "assets" -> every seeded id of that kind
      counts: dict[str, int]      # "domains", "vendors", "assets" -> A: 2 each; B, C: 1 each

  @dataclass(frozen=True)
  class World:
      a: OrgWorld; b: OrgWorld; c: OrgWorld
      global_admin: WorldUser; no_org: WorldUser; split: WorldUser; a_removed: WorldUser
      upload_dir: Path
      def org(self, name: str) -> OrgWorld: ...
      def users(self) -> list[WorldUser]: ...

  async def build_world(upload_dir: Path) -> World
  async def drop_world(world: World) -> None
  async def snapshot_org(org_id: int, upload_dir: Path) -> dict[str, list[tuple]]
  def snapshot_tables() -> list[Table]   # derived from Base.metadata, see World contents
  ```
  - `OrgWorld.ids` keys (every org gets all of them, including C):
    - `domain_id`, `vendor_id`, `upload_id`, `scan_run_id`, `asset_id`, `asset_software_id`, `finding_id`;
    - `assessment_id` (str uuid), `invite_id`, `agent_id`, `ai_generation_id`, `snapshot_id`, `stable_key`, `credential_id`, `member_user_id` (= `member.user_id`, or a seeded extra member for C).
- Produces (`tenancy/conftest.py`):
  - `world` (module scope, async): `build_world(tmp_path_factory.mktemp("uploads"))`, then on teardown `drop_world`.
  - `fresh_world` (function scope, async): the same, per test.
  - `as_user` (function scope) → `async def (user: WorldUser) -> AsyncClient`. It runs `accounts.add(user.uid, user.email)`, then `mint_id_token(signing_key, uid=..., email=...)`, then `authz_client(token)`. Registration happens on demand because stage A's `_isolate_fakes` clears the registry every test.
  - `_tenancy_settings` (autouse, function): uses `monkeypatch.setattr(settings, ...)` to set:
    - `ENABLE_M365_INTEGRATION=True`;
    - `M365_CLIENT_ID`, `M365_CLIENT_SECRET`, `M365_REDIRECT_URI` and `FRONTEND_URL` (copy `tests/test_m365_integration.py::_m365_enabled`);
    - `M365_FERNET_KEY = _TEST_FERNET_KEY`, a module constant in `_world.py` set to `Fernet.generate_key().decode()`. It must be a **str**, because the app calls `.encode()` on it (`m365_oauth.py:46`).

    `build_world` encrypts the credential's refresh token with `Fernet(_TEST_FERNET_KEY)` **directly**, not through the app's `encrypt_token`. The reason: the module-scoped `world` is set up before this function-scoped fixture, and `encrypt_token` reads `settings.M365_*` when it's called.

    It must not set `UPLOAD_DIR`: that's per world, so each world fixture sets `settings.UPLOAD_DIR = world.upload_dir` itself (module-scoped: set it on entry and restore it on teardown).
  - `_no_egress` (autouse, function): uses `monkeypatch` to replace, **at each import site**, the names below with stubs that return empty or canned results. The implementer greps for the exact sites:
    - `run_tier2_checks` in `app.api.routes.v1.domains`;
    - `run_tier1_checks`/`run_tier2_checks` where `app.services.findings_engine` imports them;
    - `app.services.ai_summary._call_gemini`;
    - `refresh_access_token` and `list_managed_devices` on the graph module `integrations.py` uses;
    - `app.workers.matcher_job.trigger_matcher_async`;
    - `fire_and_forget_normalization_log` at **every** module that imports it at module level (at least `domains.py`, `vendors.py` and `app/services/vendor_alerts.py`), **and** at `app.repositories.normalization_log_repo`, because `organizations.py` imports it inside the function.

**World contents (decided):**
- **Orgs A, B and C.** Each has `name = f"{marker} Org"`. Each also has intake fields set so that `evaluate_intake` reaches the tier that `/mine/findings` and `/mine/ai-summary` need. The implementer reads `evaluate_intake` for the minimum fields.
- **A and B users.** Each has an `owner`, an `admin` and a `member`. In each user:
  - `User.role="member"` (global);
  - `org_id` = the org, `org_role` = the role;
  - a `Membership(role=same, status="active")` row exists.

  C has only a plain member (`member_user_id`), so member routes have a target. C's `owner`, `admin` and `member` are `None`; nobody signs in as C.
- **`global_admin`:** `role="admin"`, `org_id=None`, no Membership.
- **`no_org`:** `role="member"`, `org_id=None`, no Membership. Its global role is member so that global role floors don't mask the tenancy check.
- **`split`:** `role="member"`, `org_id=A.org_id`, `org_role="admin"`, and an active `Membership` in **B** with `role="admin"`. It has no Membership in A. It is an admin in both stores so that role gates never mask which org it reaches.
- **`a_removed`:** `role="member"`, `org_id=None`, `org_role=None`, and a `Membership` in A with `role="admin"`, `status="inactive"`. That's what `remove_member` leaves behind. It proves the `status == "active"` filters.
- **Every world user** is created with `firebase_uid = uid`. Without it, `get_current_user` takes the link-by-email path, which may refuse or may write to the user row.
- **Asymmetry, so that caller routes can tell orgs apart.** A owns **2** domains, **2** vendors and **2** assets. B and C own 1 of each. `ids` holds the first of each; `ids_all` and `counts` hold all of them.
- **Per-org resources:** one each of the following, with marker strings:
  - `OrgDomain` (`f"{marker.lower()}.example.com"`), `OrgVendor`;
  - `OrgUpload`, with its file written under `upload_dir/<org_id>/` (CSV bytes);
  - `ScanRun`, then `Asset` (`tags=[marker]`), `AssetSoftware`, `AssetFinding` (`cve_id="CVE-2024-0001"`);
  - `AssessmentSubmission` (a valid `data` per the `AssessmentSubmissionCreate` schema; `is_current=True`);
  - `Invitation` (email `f"invitee-{marker}@example.com"`, token `secrets.token_urlsafe(32)`, expiry +3 days);
  - an `AgentEnrollment` via `agent_token.issue`;
  - `AISummaryGeneration`, `FindingsSnapshot`, `FindingStatus` (`stable_key=f"{marker}-key"`);
  - `IntegrationCredential(provider="m365")`, with `refresh_token_encrypted = Fernet(_TEST_FERNET_KEY).encrypt(...).decode()` directly. Don't use the app's `encrypt_token`, for the reason given under `_tenancy_settings`.
- **A's extra rows** are named distinctly from anything a builder creates:
  - vendor `f"{marker}-v1b"`;
  - asset hostname `f"{marker}-h1b"`;
  - domain `f"d2.{marker}.example.com"`.

  Builders create `-v2`, `-h2` and `new.{marker}.example.com`.
- **Emails:** `f"{key}-{marker}@example.com"`.
- **`snapshot_tables()`:** every table in `app.db` `Base.metadata` that has an `org_id` or `organization_id` column, plus `organizations` (by `id`) and `users` (by `org_id`). Deriving the list means a new org-scoped table is covered automatically. That includes `normalization_log`, `agent_scan_nonces` and `org_invites`.
- **`snapshot_org(org_id, upload_dir)`:**
  - **What it returns:** `{table_name: rows}`. Each row is a tuple of `repr()`'d column values, ordered by primary key. Using `repr` avoids comparison errors on JSONB dicts.
  - **Files:** it adds `"files"`, a sorted list of `(name, sha256)` under `upload_dir/<org_id>/`.
  - **Columns:** all of them. A denied call must not touch even `updated_at`.
- **`drop_world` order:**
  1. delete `AuditLog` and `ActivationEvent` rows by the world's org ids **and** by the world's user ids (null-org rows from the no-org and global-admin users);
  2. delete the organizations, which cascades;
  3. delete the world's users by id.

  Afterwards, assert that no `users` row with the marker in its email remains.

- [ ] **Step 1: Write the failing tests** in `test_world.py`, all using `world`:
  - `test_roles_consistent_in_both_stores`: for each of the A and B owner/admin/member users, the `users` row's `org_id`/`org_role` matches its single active Membership.
  - `test_split_user_shape`:
    - legacy `org_id == a.org_id` and `org_role == "admin"`;
    - exactly one active Membership, in B, role admin;
    - none in A.
  - `test_global_admin_and_no_org_shape`: both have `org_id is None`, no memberships, and roles `admin`/`member`.
  - `test_each_org_owns_every_kind`: for A, B and C, every key in `ids` resolves to a row whose org column equals that org's id (the upload's file exists).
  - `test_world_snapshot_stable`: `snapshot_org(a)` taken twice is equal and has a non-empty list for each table seeded above (Review Focus 2).
  - `test_snapshot_covers_every_org_table`: every table that live `information_schema.columns` shows with an `org_id`/`organization_id` column (in schema `public`, excluding `alembic_version`) is in `snapshot_tables()`. Comparing against the live DB, not `Base.metadata`, catches a model that isn't imported.
  - `test_removed_member_shape`: `a_removed` has `org_id is None` and exactly one Membership, which is in A with status `inactive`.
  - `test_minted_user_authenticates`: `as_user(world.b.member)` then `GET /api/v1/auth/me` returns 200 with `email == world.b.member.email` (a real token maps to the pre-created row).
  - `test_no_egress_stubs_installed`: each patched name resolves to the stub (Review Focus 3).
- [ ] **Step 2: Run** `pytest tests/authz/tenancy -v` (the gate command in Task 6, with `tests/authz/tenancy` as the target). Expected: a collection error, because `_world` is missing.
- [ ] **Step 3: Implement** `_world.py` and `tenancy/conftest.py` per Interfaces.
- [ ] **Step 4: Run** `pytest tests/authz -v`. Expected: the 9 new tests pass and the stage-A tests still pass. Then run the full `pytest tests/`: expected 1223 + 9 passed, 1 skipped. That full run proves the world's teardown and the settings patches don't leak into other files.
- [ ] **Step 5: Commit** `test(authz): seeded two-org fixture world with both role stores and a split user`.

### Task 2: T-TEN-10 — bind analytics events to the caller's org

**Files:**
- Modify: `backend/app/api/routes/v1/analytics.py::record_event` (L62–86)
- Modify: `backend/tests/authz/route_table.py`: the `POST /analytics/events` entry (L294–306)
- Test: `backend/tests/authz/tenancy/test_analytics_binding.py`
- Check: `backend/tests/test_analytics_events.py` must pass unchanged. Its scrub test sends `org_id: 7` as a mocked user with `org_id=7`, so the values match.

**Interfaces:**
- Consumes: `world`/`fresh_world`, `as_user`, `snapshot_org` (Task 1).
- Produces: the rule in "Decisions made in this plan". `ActivationEventCreate` keeps its optional `org_id` field, for client compatibility.

- [ ] **Step 1: Write the failing tests** (all with `fresh_world`; body `{"event_type": "dashboard_first_view", ...}`):
  - `test_event_for_other_org_refused`:
    - setup: B's member posts with `org_id = a.org_id`;
    - status is 403;
    - `snapshot_org(a)` is unchanged;
    - there is no `ActivationEvent` row with `org_id == a.org_id`.
  - `test_event_without_org_bound_to_caller`: B's member posts with no `org_id`. Expect 200, and the stored row has `org_id == b.org_id` and `user_id == b.member.user_id`.
  - `test_event_for_own_org_recorded`: B's member posts with `org_id = b.org_id`. Expect 200, and the stored `org_id == b.org_id`.
  - `test_no_org_user_event_has_no_org`: `no_org` posts with no org. Expect 200, and the stored `org_id is None`.
  - `test_global_admin_cannot_stamp_other_org`: `global_admin` posts with `org_id = a.org_id`. Expect 403.
- [ ] **Step 2: Run** the file. Expected: `test_event_for_other_org_refused`, `test_event_without_org_bound_to_caller` and `test_global_admin_cannot_stamp_other_org` fail. That's the known T-TEN-10 gap, not a stop.
- [ ] **Step 3: Implement the fix in `record_event`.**
  - Before the event-type checks, raise `HTTPException(403, "Access denied")` when `body.org_id is not None and body.org_id != current_user.org_id`.
  - Build the event with `org_id=current_user.org_id`.
  - Update the module docstring with one line on the binding.
- [ ] **Step 4: Update the route-table entry:**
  - `RouteSpec("organization-scoped", min_role=None, org_from="caller", note="T-TEN-10 fixed: org bound to the caller; a differing body org is refused")`.
  - Also amend the `route_table.py` module docstring: org-check and `min_role` behaviour for org-scoped routes is proven by `tests/authz/tenancy/`, not by `check_table`.
- [ ] **Step 5: Run** `pytest tests/authz tests/test_analytics_events.py -v`. Expected: all pass, including `test_every_route_classified`.
- [ ] **Step 6: Commit** `fix(analytics): bind activation events to the caller's organization`. The body uses planning-level wording: "events were stored with a client-supplied org id; the server now uses the caller's org (T-TEN-10)".

### Task 3: Case table, coverage test, positive control

**Files:**
- Create: `backend/tests/authz/tenancy/_cases.py`
- Test: `backend/tests/authz/tenancy/test_cases.py`

**Interfaces:**
- Consumes: `ROUTES`, `RouteSpec` (`route_table.py`); `World`, `OrgWorld` (Task 1).
- Produces:
  ```python
  @dataclass(frozen=True)
  class Req:
      method: str
      url: str                          # fully formatted, e.g. f"/api/v1/organizations/{t.org_id}/vendors"
      params: dict[str, str] | None = None
      json: dict | None = None
      files: dict[str, tuple[str, bytes, str]] | None = None

  @dataclass(frozen=True)
  class Case:
      build: Callable[[World, OrgWorld], Req]   # target org: names t.org_id and t.ids[...]
      allowed: int                              # status for the target org's owner (positive control)
      denial: Literal[403, 404] | None          # status for B's owner targeting A; None = caller route with nothing to target
      admin_bypass: bool                        # global admin (no org) gets `allowed` on target A
      split_reaches: frozenset[str]             # subset of {"A", "B"} the split user gets `allowed` on
      denial_detail: str | None = None          # the B owner's exact `detail`, e.g. "Access denied" (proves the tenancy check, not a role gate, refused it)
      shows_marker: bool = False                # an allowed response body contains the target org's marker
      belongs_to: Callable[[dict, OrgWorld], bool] | None = None  # an allowed body is t's data (org_id == t.org_id, ids in t, counts == t.counts)
      org_free: bool = False                    # response carries no org data (intake-preview only); needs a note
      note: str = ""

  CASES: dict[tuple[str, str], Case]            # key = ROUTES key
  def org_scoped_keys() -> set[tuple[str, str]]  # keys in ROUTES with cls == "organization-scoped"
  ```

**Builder rules (decided):**
- **Valid requests only.** Send real bodies and files, so that 422 can never stand in for a denial. Use these minimal examples:
  - vendor CSV: `vendor_name\n{marker}-v2\n`;
  - inventory CSV: `hostname\n{marker}-h2\n`, with `?confirm=true` on import;
  - upload: a `text/csv` file;
  - invites and member updates use the JSON key `org_role` (the schema alias). Invites go to a fresh `f"new-{uuid}@example.com"` with no role;
  - a member update targets `t.ids["member_user_id"]` with `{"org_role": "member"}`;
  - M365 routes take `?org_id=`.
- **Caller routes** (`org_from="caller"`): `build` ignores `t` unless the route takes a resource id. In that case it uses `t`'s id: agents rotate/delete, `ai-summary/history/{id}`, `findings/history/{id}`. For analytics, the body `org_id` is `t.org_id`.
  - With a resource id (or analytics' body org): `denial` is 404 for an id route and 403 for analytics.
  - Without one: `denial=None`.
- **`allowed` must be 2xx, except in these cases**, each pinned with a `note`:
  - a route the world can't drive to 2xx without an external service. For example, if `/mine/ai-summary` still needs more than the stubbed Gemini, pin its real status with the reason;
  - a status that is only reachable after the org check. `POST /assessments/` returns 409 because the world seeds a current submission, and the 409 is raised after `_ensure_org_access`.

  `allowed` may never be 401, 403 or 404: otherwise "reached" and "denied" would be indistinguishable.
- **`denial_detail` is pinned for every case with a `denial`.** The values are `"Access denied"` (`check_org_access`), `"Access denied for this organization"` (membership), and the 404 detail on id routes.
- **Every caller case with `denial=None` sets `shows_marker` or `belongs_to`**, or sets `org_free=True` with a `note`. `org_free` is a new `Case` field, `bool = False`, used only by `POST /mine/intake-preview`, a pure evaluation with no org data. Use `belongs_to` where the body has no seeded string:
  - counts route: compare with `t.counts` (A's are 2 and B's are 1, so the wrong org shows);
  - org-id route: compare `org_id` (for example `SnapshotDetail.org_id`);
  - list route: every returned id is in `t.ids_all` for that kind, or equals `t.ids[...]` for single-row kinds.
- **`shows_marker=True`** on every list or detail read whose response includes a seeded string field: vendors, domains, uploads list, assets, members, invites, `/mine/vendor-alerts` if it lists vendor names, `/agents` and similar.
- **Expected pinned values**, from the handler analysis. The implementer confirms each one against the run. A deviation is reported to the controller, never silently re-pinned.
  - `check_org_access` / `_ensure_org_access` routes (vendors, domains, uploads, inventory, assessments, M365):
    - `denial=403`, `admin_bypass=True`, `split_reaches={"A"}`.
  - `GET /organizations/{org_id}`:
    - `denial=403`, `admin_bypass=True`, `split_reaches={"A","B"}` (legacy or Membership).
  - `PUT /organizations/{org_id}`:
    - `denial=403`, `admin_bypass=True`, `split_reaches={"A"}`.
  - The 14 members/invites routes (`require_same_org_membership` / `require_membership_role`):
    - `denial=403`, `admin_bypass=False`;
    - `split_reaches={"A","B"}`: B through the Membership, A through the legacy fallback. This is the T-TEN-12 drift.
  - `/mine/*`, `/anomalies/vendors`, `/agents*` (`get_current_org`):
    - `admin_bypass=False`, because a global admin with no org gets 403;
    - `split_reaches={"A"}`;
    - `denial`: 404 on id routes, `None` otherwise.
    - Exception: `POST /mine/intake-preview` needs no org, so `admin_bypass=True` with a note.
  - Analytics (after Task 2): `denial=403`, `admin_bypass=False`, `split_reaches={"A"}`.

- [ ] **Step 1: Write the tests** in `test_cases.py`:
  - `test_every_org_scoped_route_has_a_case`: `set(CASES) == org_scoped_keys()`. The message lists the missing and stale keys separately (Review Focus 5).
  - `test_case_table_is_consistent`:
    - `denial in {403, 404, None}`;
    - `split_reaches <= {"A","B"}`;
    - `denial is None` only when `ROUTES[key].org_from == "caller"`;
    - `allowed not in {401, 403, 404}`;
    - `denial_detail` is set iff `denial` is set;
    - a `denial=None` case has `shows_marker or belongs_to or org_free`, and `org_free` implies `note`.
  - `test_target_owner_allowed[key]` (parametrised over `CASES`, ids `f"{method} {path}"`, `fresh_world`):
    - setup: `as_user(world.a.owner)` sends `case.build(world, world.a)`;
    - `status == case.allowed`;
    - if `shows_marker`, `world.a.marker in response.text.lower()`;
    - if `belongs_to`, `case.belongs_to(response.json(), world.a)`;
    - never `world.b.marker in response.text.lower()` (Review Focus 1).
- [ ] **Step 2: Run** with an empty `CASES`. Expected: the coverage test fails and lists all 76 keys. That's the worklist.
- [ ] **Step 3: Implement `_cases.py`.** Fill it module by module, grouped in the same order as `route_table.py`, by the rules above.
- [ ] **Step 4: Run** `pytest tests/authz/tenancy/test_cases.py -v`. Expected: all pass. For any `allowed` mismatch, fix the builder, not the pin, unless the handler really returns that status. In that case add a `note`.
- [ ] **Step 5: Commit** `test(authz): per-route request builders for every organization-scoped route`.

### Task 4: Cross-tenant denial sweep and caller isolation

**Files:**
- Test: `backend/tests/authz/tenancy/test_cross_tenant.py`

**Interfaces:**
- Consumes: `CASES`, `Case`, `Req` (Task 3); `world`, `as_user`, `snapshot_org` (Task 1).

The callers are `b_owner`, `b_admin`, `b_member`, `no_org` and `a_removed` (A's inactive membership), parametrised as `caller` over those five keys. Body checks compare case-insensitively: `marker in response.text.lower()`, with emails lowercased too. The cases are `CASES` items. `test_cross_tenant_denied` uses the module-scoped `world`, because a denied call must leave it unchanged.

- [ ] **Step 1: Write the tests:**
  - `test_cross_tenant_denied[key-caller]`, for cases with `denial is not None`:
    - setup: `before = snapshot_org(a)`; send `case.build(world, world.a)` as the caller;
    - assert the status is in `{403, 404}`;
    - for `b_owner`, assert `status == case.denial` and `response.json()["detail"] == case.denial_detail` exactly (Review Focus 4);
    - assert `snapshot_org(a) == before`;
    - assert `world.a.marker` and every A user's email are absent from `response.text`.
  - `test_caller_route_sees_only_own_org[key-caller]`, for cases with `denial is None`:
    - setup: `before = snapshot_org(a)`; send `case.build(world, world.b)`;
    - the expected status depends on the caller:
      - `no_org` and `a_removed`: 403, except on `org_free` cases, where it's `case.allowed`;
      - `b_member` on a route whose `ROUTES[key].min_role == "org:admin"`: 403;
      - otherwise: `case.allowed` (which may be a pinned non-2xx such as 503 or 422);
    - if the status is 2xx and the caller has an org (that is, it's a B user):
      - `world.a.marker not in response.text.lower()`;
      - if `shows_marker`, `world.b.marker in response.text.lower()`;
      - if `belongs_to`, `case.belongs_to(body, world.b)` and `not case.belongs_to(body, world.a)`;
    - in every case, `snapshot_org(a) == before`.

    This test uses **`fresh_world`**, not `world`. Allowed caller calls write to B's own rows (feedback, enroll, intake skip), and a repeat on a shared world could return 409 instead of the pinned status.
  - `test_agent_token_scoped_to_its_org`: an agent token issued for B (`agent_token.issue` in the test) on `GET /api/v1/inventory/scans/{a.ids["scan_run_id"]}` returns 404, and A is unchanged. This route is in the `agent` class, outside the 76, and the case is cheap because the world already issues tokens.
- [ ] **Step 2: Run** `pytest tests/authz/tenancy/test_cross_tenant.py -v`. Expected: all pass, about 76 × 5 cases. **If any case gets `allowed` or leaks a marker, apply the severe-finding stop** (Global Constraints) before anything else.
- [ ] **Step 3: Commit** `test(authz): cross-tenant sweep over every organization-scoped route`.

### Task 5: Global-admin boundary and the split user

**Files:**
- Test: `backend/tests/authz/tenancy/test_global_admin.py`
- Test: `backend/tests/authz/tenancy/test_split_user.py`

**Interfaces:**
- Consumes: `CASES` (Task 3); `fresh_world`, `as_user`, `snapshot_org` (Task 1).

- [ ] **Step 1: Write the tests** (function-scoped `fresh_world`: allowed calls write):
  - `test_global_admin_boundary[key]`:
    - setup: send `case.build(world, world.a)` as `global_admin`;
    - if `admin_bypass`: `status == case.allowed`;
    - otherwise: the status is in `{403, 404}` and `snapshot_org(a)` is unchanged.

    The members routes landing on the `False` side is the spec's "member routes do not let it bypass".
  - `test_split_user_reach[key]`:
    - setup: for target in A, B, C: send `case.build(world, world.org(target))` as `split`, then classify the result as `"reached"` (status == `case.allowed`), `"denied"` (403/404) or unexpected (fail);
    - **C first:** assert C was denied, with the message `"split user reached org C: severe-finding stop"`; its `snapshot_org(c)` is unchanged;
    - then assert `{t for t in "AB" if reached[t]} == case.split_reaches`.

    For caller routes with no target (`denial is None`), call once with `case.build(world, world.a)` and assert `status == case.allowed`. The split user resolves to A through the legacy store, so (body checks lowercased):
    - if `shows_marker`, A's marker is present and B's is absent;
    - if `belongs_to`, it holds for A and not for B.
- [ ] **Step 2: Run both files.** Expected: all pass. **A reach on C is a severe-finding stop.** A mismatch on A or B goes to the controller; it isn't re-pinned silently.
- [ ] **Step 3: Commit** `test(authz): global-admin boundary and split role-store user per route`.

### Task 6: Threat model, docs, gate, PR

**Files:**
- Modify: `docs/security/threat_model.md`:
  - L15 (Rules);
  - T-TEN-10 (L182);
  - T-TEN-12 (L184);
  - the Findings item 6 (L293), with a "fixed in S4-B" suffix;
  - the OPEN RISK S4 row (L307).
- Modify: `README.md:162`
- Modify: `docs/PRODUCT_VIABILITY_ROADMAP.md:277`

- [ ] **Step 1: Rules L15.** Replace "plus a shared OPEN row against S4's real-verification suite" with wording that points tenancy at T-TEN-12, which is now TEST, and AUTH at T-AUTH-07.
- [ ] **Step 2: T-TEN-10 → TEST.**
  - Evidence: `` `backend/tests/authz/tenancy/test_analytics_binding.py::test_event_for_other_org_refused` ``.
  - Notes start: `real-verification: minted tokens through the real verifier; the route now takes the event's org from the caller and refuses a differing body org (403, nothing written).`
- [ ] **Step 3: T-TEN-12 → TEST.**
  - Evidence: `` `backend/tests/authz/tenancy/test_cross_tenant.py::test_cross_tenant_denied` ``.
  - Notes start: `real-verification: every organization-scoped route in route_table.py has a case (coverage test); B's roles and a no-org user are denied 403/404 on A's resources with A's rows unchanged; the global-admin boundary and the split user are pinned per route.`
  - Then add one planning-level sentence recording the drift. For example: "A user whose legacy org and Membership disagree reaches both claimed orgs on Membership-based routes and only the legacy org elsewhere; recorded, not fixed (merging the stores is out of S4)."
  - Drop "no test runs the real tenancy dependencies" from the Threat column only if the checker allows it. Otherwise keep the Threat text as is, since IDs and threats are stable.
- [ ] **Step 3b: Cross-references.** T-ENR-01, T-ENR-03, T-ING-08 and T-AI-08 (L113, L115, L198, L232) say "see T-TEN-12" next to stub-only tests. Where `tenancy/` now covers the route, append "; covered under real verification by `tests/authz/tenancy/`". The rows keep their class.
- [ ] **Step 4: OPEN RISK S4 row.** Remove T-TEN-10 and T-TEN-12, leaving 11 rows.
- [ ] **Step 5: Recount** the rows by Class. Expected: 110 total, 41 CONTROL / 24 TEST / 18 ACCEPTED / 27 OPEN. Verify by counting, and use the real numbers if they differ.
  - Update `README.md:162`.
  - `docs/README.md:23` ("110 threats") stays unchanged; check it.
- [ ] **Step 6: Roadmap L277.** Append: `Stage B (cross-tenant sweep over 76 organization-scoped routes; T-TEN-10 fixed) — PR #TBD.` The controller fills the number after the PR exists, as in stage A.
- [ ] **Step 7: Gate**, each its own call. Reuse the network, container and volume if they exist (`docker ps -a --filter name=ht-s4-pg`); otherwise recreate them per plan A Task 4 Step 6.
  - Backend:
    ```
    MSYS_NO_PATHCONV=1 docker run --rm --network ht-s4-net -v C:/dev/ht-s4-b/backend:/app -v ht-s4-venv:/venv -v ht-pipcache:/root/.cache/pip -w /app -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@ht-s4-pg:5432/cyber_threat_test_db -e APP_ENV=testing python:3.11-slim sh -c "python -m venv /venv && /venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt && /venv/bin/ruff check app tests evals && /venv/bin/ruff format app tests evals --check && /venv/bin/alembic -c app/db/alembic.ini upgrade head && /venv/bin/pytest tests/ -q"
    ```
    Expected: ruff clean; pytest = 1223 + the new tests, 0 failed, 1 skipped. Record the authz runtime, because the sweep is several hundred cases. If it adds more than about 3 minutes, report that to the controller rather than trimming cases.
  - `python .github/scripts/check_threat_model.py docs/security/threat_model.md`: expected exit 0.
  - `python -m unittest discover -s .github/scripts`: expected OK (65).
- [ ] **Step 8: Commit** `docs(threat-model): T-TEN-10 and T-TEN-12 closed by the S4 cross-tenant suite`.
- [ ] **Step 9: The controller pushes and opens the draft PR.**
  - **PR settings:** target `main`, titled `S4-B: cross-tenant sweep, T-TEN-10 fix`. Verify `baseRefName == main`. Don't mark it ready.
  - **Body:**
    - starts with `> Stacked on #226`;
    - the world summary;
    - the 403-vs-404 table, generated from `CASES` (route, B-owner denial);
    - the written answer to "why 403 here and 404 there" (from "Decisions made in this plan");
    - the global-admin table: the bypass routes and the no-bypass routes;
    - the split-user result **grouped by mechanism**, not per route: Membership-based routes (n) reach both claimed orgs, while legacy-store and `get_current_org` routes (n) reach the legacy org only, and org C is never reached;
    - the T-TEN-10 change, at planning level;
    - the threat-model counts;
    - `[K]` so far: 1 (analytics).
