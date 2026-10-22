# S4 stage A: authorization harness, real verification, route table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `backend/tests/authz/` suite that runs Firebase ID-token verification for real (locally signed key, no mock), proves forged/expired/revoked/disabled tokens are rejected, and enumerates every app route against a committed classification table.

**Architecture:** A folder-local conftest overrides the global autouse `verify_id_token` mock by name, starts a real default `firebase_admin` app with a test project id, and mounts two `requests` transport adapters on the SDK's own sessions: one serves our X.509 cert at Google's cert URL, one fakes Identity Toolkit `accounts:lookup` for `check_revoked=True`. A Python route table plus a dependency-tree walker make CI fail on any unclassified, stale or mislabelled route.

**Tech Stack:** Python 3.11, FastAPI 0.133, firebase-admin 6.4.0, google-auth 2.62.0, PyJWT 2.15.1, cryptography 50.0.2, pytest 9 + pytest-asyncio 1.4 (`asyncio_mode = auto`, session loop), httpx `ASGITransport`.

**Spec:** `docs/superpowers/specs/2026-10-22-s4-authorization-assurance-design.md` (decisions 1–3; stage A row).

## Global Constraints

- Worktree `C:/dev/ht-s4-a`, branch `feat/s4-authz-suite`, stacked on #225 (`docs/s3-threat-model`). Commit as `git -C C:/dev/ht-s4-a -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`. No Claude attribution. One shell command per Bash call.
- **No new dependency.** `cryptography`, `pyjwt`, `requests`, `google-auth` are already installed via firebase-admin.
- **Patch only the network edge.** Nothing in `firebase_admin.auth`, `firebase_admin._token_gen`, `firebase_admin._auth_client`, `google.oauth2.id_token` or `google.auth.jwt` may be patched or monkeypatched. Mounting adapters on the SDK's `requests` sessions is the only allowed hook.
- **Existing tests stay unchanged** and keep the autouse mock. Only files under `backend/tests/authz/` are new test code.
- **Severe-finding stop:** if classifying a route shows org data reachable without an org check, an auth bypass, or a leaked credential not already in `docs/security/threat_model.md`, stop, commit nothing about it, and report to the controller in chat only. T-TEN-05 and T-TEN-10 are already known; record them in the table's `note`, don't stop.
- **Public repo:** table notes and commit messages describe gaps at planning level only (no request recipes).
- Lint: `ruff check app tests evals` and `ruff format app tests evals --check` from `backend/`. Ruff rules include `FBT` (no boolean positional args: make flags keyword-only) and `N`.
- Test project id: `ht-authz-test`. Cert URL (from `_token_gen.ID_TOKEN_CERT_URI`): `https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com`. Issuer: `https://securetoken.google.com/ht-authz-test`. Identity Toolkit lookup: `POST https://identitytoolkit.googleapis.com/v1/projects/ht-authz-test/accounts:lookup`, body `{"localId": [uid]}`, response `{"users": [{"localId", "email", "emailVerified", "disabled", "validSince"}]}` (`validSince` is a string of epoch **seconds**); `{}` means not found (the SDK raises `UserNotFoundError`, a `FirebaseError`, so the route returns 401).
- App clock skew is 10 s (`auth.py::_TOKEN_CLOCK_SKEW_SECONDS`). Rate limit on `/auth/me` is `30/minute` (`slowapi`, in-memory): the suite resets the limiter before each test.

## Review Focus

1. **The mock silently comes back** (a future conftest edit, or a fixture-name typo in the override): the guard test must fail, not skip. Pinned in Task 1 (`test_verify_id_token_is_real`, `test_cert_fake_was_hit`).
2. **A cached or real Google cert stands in for ours** (e.g. CacheControl serves a cached response, or the adapter prefix doesn't match): the forged-key test would then pass for the wrong reason. Pinned in Task 1 (`test_cert_fake_was_hit` asserts the adapter's hit count rises on each verification).
3. **A denied token returns 500 instead of 401** (e.g. `UserNotFoundError` or `CertificateFetchError` escaping as an unhandled error): every Task 2 test asserts exactly 401. Add `test_unknown_firebase_account_rejected` (token for a uid the fake doesn't know).
4. **A route is labelled `public` to silence the enumerator**: Task 3's cross-check fails it. Add `test_cross_check_catches_mislabel` (feed the checker a synthetic entry and assert it reports a problem).
5. **The default Firebase app leaks into other test files** (initialized by the suite and never deleted, so later tests see a live app): Task 1's fixture deletes it on teardown. Add `test_firebase_app_torn_down` as a final-ordered check, or assert `firebase_admin._apps == {}` in the fixture's teardown.

---

### Task 1: Real-verification harness and guard

**Files:**
- Create: `backend/tests/authz/__init__.py` (empty)
- Create: `backend/tests/authz/_issuer.py`
- Create: `backend/tests/authz/_fakes.py`
- Create: `backend/tests/authz/conftest.py`
- Test: `backend/tests/authz/test_harness.py`

**Interfaces:**
- Produces (`_issuer.py`):
  - `PROJECT_ID = "ht-authz-test"`, `KID = "authz-test-kid"`, `ISSUER = "https://securetoken.google.com/ht-authz-test"`.
  - `class SigningKey`: `private_key` (RSA 2048), `cert_pem: str` (self-signed X.509, valid now−1 day to now+1 day). `SigningKey.generate() -> SigningKey`.
  - `mint_id_token(key: SigningKey | None, *, uid: str, email: str, email_verified: bool = True, iat: int | None = None, exp: int | None = None, aud: str = PROJECT_ID, iss: str = ISSUER, kid: str = KID, alg: str = "RS256", hs_secret: str = "authz-hs-secret", extra: dict | None = None) -> str`. Defaults: `iat = now - 5`, `exp = iat + 3600`, `auth_time = iat`, `sub = uid`, `firebase = {"sign_in_provider": "password", "identities": {}}`. `alg="HS256"` signs with `hs_secret`; `alg="none"` produces an unsigned token (key ignored). Uses PyJWT with `headers={"kid": kid}`.
- Produces (`_fakes.py`):
  - `class CertAdapter(requests.adapters.BaseAdapter)`: `__init__(self, cert_pem_by_kid: dict[str, str])`; `hits: int`; `send()` returns 200 `application/json` body `json.dumps(cert_pem_by_kid)` with `Cache-Control: no-store`.
  - `class FakeAccounts`: `add(uid: str, email: str, *, email_verified: bool = True) -> None`; `disable(uid: str) -> None`; `revoke(uid: str, *, at: int) -> None` (sets `validSince = str(at)`); `lookup(uid: str) -> dict | None`.
  - `class IdentityToolkitAdapter(requests.adapters.BaseAdapter)`: `__init__(self, accounts: FakeAccounts)`; `hits: int`; handles only `POST .../projects/ht-authz-test/accounts:lookup` (anything else: 404 JSON error body, so an unexpected SDK call is visible); returns `{"users": [record]}` or `{}`.
- Produces (`conftest.py`):
  - fixture `_mock_firebase_verify` (same name as the global one, autouse, no-op: `yield`), which overrides the parent's for this folder.
  - fixture `signing_key` (package scope) → `SigningKey`.
  - fixture `firebase_test_app` (package scope, autouse) → `(CertAdapter, IdentityToolkitAdapter, FakeAccounts)`. Fails loudly if `firebase_admin._apps` is non-empty on entry. Calls `firebase_admin.initialize_app(credential=_StaticCredential(), options={"projectId": PROJECT_ID})` (the **default** app, because `auth.py` calls `firebase_auth.verify_id_token` without `app=`). Gets the client via `firebase_admin.auth._get_client(app)`, then mounts `CertAdapter` on `client._token_verifier.request.session` at the cert URL and `IdentityToolkitAdapter` on `client._user_manager.http_client.session` at `https://identitytoolkit.googleapis.com/`. Teardown: `firebase_admin.delete_app(app)` and assert `firebase_admin._apps == {}`.
  - `_StaticCredential(firebase_admin.credentials.Base)`: `get_credential()` returns a `google.auth.credentials.Credentials` subclass with `token = "authz-test-access-token"`, `expiry = None`, and `refresh()` a no-op.
  - fixtures `cert_adapter`, `accounts` (function scope; `accounts` clears the registry before each test) derived from `firebase_test_app`.
  - fixture `_reset_limiter` (autouse, function scope): `app.core.limiter.limiter.reset()`.
  - fixture `authz_client` → `async def (token: str | None) -> AsyncClient` factory. Builds clients on `ASGITransport(app=app.main.app)`; sets `Authorization: Bearer <token>` when given; closes them on teardown. Never reuse the global `client` fixture.
  - fixture `new_user(accounts, signing_key)` → `Callable[..., tuple[str, str]]`: registers a fresh `uid = f"authz-{uuid4().hex[:12]}"` with a `unique_email()` (import from `tests.conftest`) in `FakeAccounts` and returns `(uid, email)`.

- [ ] **Step 1: Write the failing tests** in `test_harness.py`:
  - `test_verify_id_token_is_real`: `assert not isinstance(firebase_admin.auth.verify_id_token, unittest.mock.NonCallableMock)` and `assert firebase_admin.auth.verify_id_token.__module__ == "firebase_admin.auth"`.
  - `test_valid_token_accepted`: register a user, mint a token, `GET /api/v1/auth/me` → 200 and `body["email"] == email`.
  - `test_cert_fake_was_hit`: record `cert_adapter.hits`, make two valid `/auth/me` calls, assert hits rose by ≥ 2. Also assert `IdentityToolkitAdapter.hits` rose (proves `check_revoked=True` reached the fake).
- [ ] **Step 2: Run and confirm they fail** (module import errors): `pytest tests/authz -v` inside the gate container (see Task 4 for the exact command). Expected: collection errors for the missing `_issuer` / `_fakes`.
- [ ] **Step 3: Implement `_issuer.py`, `_fakes.py`, `conftest.py`** per the Interfaces block.
- [ ] **Step 4: Run** `pytest tests/authz -v`. Expected: 3 passed. Then run the full `pytest tests/` and confirm the pass count equals the baseline plus 3, with no newly failing test (proves the override is folder-local and teardown is clean).
- [ ] **Step 5: Commit** `test(authz): real Firebase verification harness with local signing key`.

### Task 2: Claim-2 tests: rejected tokens (T-AUTH-07)

**Files:**
- Test: `backend/tests/authz/test_token_verification.py`

**Interfaces:**
- Consumes: `mint_id_token`, `SigningKey`, `FakeAccounts`, `authz_client`, `new_user`, `signing_key` from Task 1.

Every test below asserts `status_code == 401` exactly. The human-route target is `GET /api/v1/auth/me`; agent-route targets are `POST /api/v1/inventory/scans` (body `{}`) and `GET /api/v1/inventory/scans/1`.

- [ ] **Step 1: Write the tests:**
  - `test_forged_signature_rejected`: token signed by a fresh `SigningKey.generate()` with the same `KID`.
  - `test_expired_token_rejected`: `iat = now - 3630`, `exp = now - 30` (past the 10 s skew; no sleep).
  - `test_wrong_audience_rejected`: `aud="other-project"`.
  - `test_wrong_issuer_rejected`: `iss="https://securetoken.google.com/other-project"`.
  - `test_hs256_token_rejected`: `alg="HS256"`.
  - `test_alg_none_token_rejected`: `alg="none"`.
  - `test_revoked_token_rejected`: token `iat = now - 60`; `accounts.revoke(uid, at=now - 10)`.
  - `test_token_after_revocation_accepted`: `accounts.revoke(uid, at=now - 120)`, token `iat = now - 5` → **200** (control for the previous test).
  - `test_disabled_user_rejected`: `accounts.disable(uid)`.
  - `test_unknown_firebase_account_rejected`: valid signature, uid never added to `FakeAccounts`.
  - `test_missing_authorization_rejected`: no header.
  - `test_malformed_bearer_rejected`: `Bearer not-a-jwt`.
  - `test_agent_token_on_human_route_rejected`: `Bearer ht_abcd1234_` + 43 url-safe chars.
  - `test_firebase_token_on_agent_routes_rejected`: a valid minted token on both agent routes.
  - For each rejection test, also assert no `User` row was created for that uid (query by `firebase_uid` through `app.db.engine` session). A rejected token must not auto-create an account.
- [ ] **Step 2: Run** `pytest tests/authz/test_token_verification.py -v`. Expected: all pass. The harness is already real, so these should pass on first run. **If any returns 200 or 500, stop and report to the controller (severe-finding rule) before changing anything.**
- [ ] **Step 3: Mutation check (not committed):** temporarily edit `auth.py` to call `verify_id_token(token, check_revoked=False, ...)`, run the file, and confirm `test_revoked_token_rejected` and `test_disabled_user_rejected` fail. Revert the edit and confirm `git -C C:/dev/ht-s4-a diff --stat backend/app` is empty. Record the result in the PR body.
- [ ] **Step 4: Commit** `test(authz): reject forged, expired, revoked and disabled ID tokens`.

### Task 3: Route classification table, enumerator and dependency cross-check

**Files:**
- Create: `backend/tests/authz/route_table.py`
- Create: `backend/tests/authz/_routes.py`
- Test: `backend/tests/authz/test_route_table.py`
- Modify: `backend/tests/authz/conftest.py` (add `pytest_terminal_summary`)

**Interfaces:**
- Produces (`route_table.py`):
  ```python
  RouteClass = Literal["public", "authenticated-global", "organization-scoped", "agent", "administrator"]
  OrgFrom = Literal["path", "caller", "resource"]

  @dataclass(frozen=True)
  class RouteSpec:
      cls: RouteClass
      min_role: str | None = None   # "viewer"|"member"|"admin" (global) or "org:member"|"org:admin"|"org:owner"
      org_from: OrgFrom | None = None
      flag: str | None = None
      note: str = ""

  def build_table(entries: list[tuple[str, str, RouteSpec]]) -> dict[tuple[str, str], RouteSpec]: ...
      # raises ValueError("duplicate: METHOD path") on a repeated key (a dict literal would silently keep the last one)

  ROUTES: dict[tuple[str, str], RouteSpec] = build_table([...])   # key: (METHOD, route.path template), e.g. ("GET", "/api/v1/auth/me")
  ```
- Produces (`_routes.py`):
  - `enumerate_routes(app: FastAPI) -> list[tuple[str, str, BaseRoute]]`: every `(method, path, route)` in `app.routes`, one per method, skipping implicit `HEAD`/`OPTIONS`. Non-API Starlette routes (`/docs`, `/openapi.json`, `/redoc`, `/docs/oauth2-redirect`) are included with their methods.
  - `dependency_calls(route: BaseRoute) -> set[Callable]`: the `call` of every node in `route.dependant`'s tree, recursively (router-level `dependencies=` are part of that tree). Empty set for non-API routes.
  - `check_table(app: FastAPI, table: dict[tuple[str, str], RouteSpec]) -> list[str]`: the problem list. Rules:
    - a route missing from the table: `"unclassified: METHOD path"`;
    - a table key with no route: `"stale: METHOD path"`;
    - `org_from` set iff `cls == "organization-scoped"`;
    - `public` → none of `get_current_user`, `get_agent_from_token` in `dependency_calls`;
    - `agent` → `get_agent_from_token` in calls and `get_current_user` not in calls;
    - `authenticated-global`, `organization-scoped`, `administrator` → `get_current_user` in calls;
    - `administrator` → `require_role("admin")` in calls (`require_role` is `functools.cache`d, so identity comparison works).
- Consumes: `app.main.app`, `app.api.routes.v1.auth.get_current_user`, `app.core.dependencies.get_agent_from_token`, `app.core.dependencies.require_role`.

**Classification rules for filling `ROUTES`** (read each handler; don't guess from the path):
- `public`: no auth dependency. Expected members include `/health`, `/api/v1/health`, `/`, the landing-page public stats, data-status, `/api/v1/ingest/health`, invite lookup by token if it has no auth, the M365 OAuth callback if unauthenticated, and docs/openapi (note T-PLAT-08 ACCEPTED).
- `organization-scoped`: the handler reads or writes rows owned by one org. `org_from="path"` when an `{org_id}` path param is checked (`check_org_access`, `require_same_org_membership`, `require_membership_role`); `"caller"` when the org comes from `get_current_org` / `current_user.org_id`; `"resource"` when it comes from a looked-up resource id. `min_role` is what the route **enforces today**. Where T-TEN-05 says the intent is higher, add `note="T-TEN-05: intent org:admin"`. The analytics event route gets `note="T-TEN-10"`.
- `administrator`: requires the global admin role.
- `authenticated-global`: any signed-in user, no org data (global feeds behind `require_role("viewer")`, `/auth/me`, onboarding org creation).
- `agent`: the two `/api/v1/inventory/scans` agent routes.
- M365 routes: their real class plus `flag="ENABLE_M365_INTEGRATION"`.
- Both aliases of doubled paths (`/orgs/...` and `/organizations/...`) are separate entries.
- If a route's real behaviour fits no class, or an org-scoped route has no visible org check in its dependencies **or** body: stop and report to the controller (severe-finding rule).

- [ ] **Step 1: Write the failing tests** in `test_route_table.py`:
  - `test_every_route_classified`: `assert check_table(app, ROUTES) == []` (the failure message lists the problems, one per line).
  - `test_cross_check_catches_mislabel`: copy `ROUTES`, relabel `("GET", "/api/v1/auth/me")` as `RouteSpec("public")`, and assert a problem mentioning that path is returned. Remove one entry and assert `"unclassified: GET /api/v1/auth/me"`. Add `("GET", "/api/v1/nope")` and assert `"stale: GET /api/v1/nope"`.
  - `test_duplicate_entry_rejected`: `build_table` with the same `("GET", "/x")` twice raises `ValueError` matching `"duplicate: GET /x"`.
  - `test_agent_routes_are_agent_only`: the two inventory scan agent entries have `cls == "agent"`.
  - `test_route_counts_cover_all`: `sum(Counter(s.cls for s in ROUTES.values()).values()) == len(enumerate_routes(app))`.
- [ ] **Step 2: Run** with an empty `ROUTES = {}`. Expected: `test_every_route_classified` fails, listing every route as unclassified. Save that list: it's the worklist.
- [ ] **Step 3: Implement `_routes.py`**, then fill `ROUTES` from the worklist by the rules above, module by module, with a one-line `note` where the class isn't obvious from the path.
- [ ] **Step 4: Add `pytest_terminal_summary(terminalreporter)`** to the authz conftest. It writes `authz route table: N routes — public a, authenticated-global b, organization-scoped c, agent d, administrator e` (plus `flagged f`) via `terminalreporter.write_line`.
- [ ] **Step 5: Run** `pytest tests/authz -v`. Expected: all pass, and the summary line is printed. Record the counts for the PR body.
- [ ] **Step 6: Hand the controller the full table diff for review before committing.** Classification is a security judgment, so the controller checks every `public` and `organization-scoped` entry against its handler.
- [ ] **Step 7: Commit** `test(authz): route classification table with enumerator and dependency cross-check`.

### Task 4: Threat model, docs, gate

**Files:**
- Modify: `docs/security/threat_model.md`: line 15 (Rules), the T-AUTH-07 row (L167), the OPEN RISK index S4 row (L307)
- Modify: `README.md:162`
- Modify: `docs/PRODUCT_VIABILITY_ROADMAP.md` (S4 section, after L277)

- [ ] **Step 1: Rules line 15.** Append a sentence: tests under `backend/tests/authz/` disable the mock and verify real locally signed tokens through `firebase_admin.auth.verify_id_token(check_revoked=True)`, so they can be TEST.
- [ ] **Step 2: T-AUTH-07 → TEST.**
  - Evidence: `` `backend/tests/authz/test_token_verification.py::test_forged_signature_rejected` ``. Add more ids only if the checker accepts several; otherwise name the file's key test and list the rest in Notes.
  - Notes start with `real-verification: locally signed RS256 key served at the SDK's cert URL; check_revoked=True against a fake Identity Toolkit at the HTTP layer; the guard test fails if the mock returns.`
  - Leave the other AUTH/TEN rows alone: they move in stages B and C.
- [ ] **Step 3: Remove T-AUTH-07 from the OPEN RISK index S4 row.**
- [ ] **Step 4: Recount.** Count the rows by class in `threat_model.md`. The expected result is 110 total, with 41 CONTROL, 22 TEST, 18 ACCEPTED and 29 OPEN. Update `README.md:162` to match. `docs/README.md:23` says "110 threats", which is unchanged. Check it anyway.
- [ ] **Step 5: Roadmap.** Under S4, add `Stage A (harness, real verification, route table: N routes) — PR #<n>`. Don't mark S4 done.
- [ ] **Step 6: Gate** (each its own call):
  - Network and DB:
    - `docker network create ht-s4-net`
    - `docker run -d --name ht-s4-pg --network ht-s4-net -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=cyber_threat_test_db postgres:15-alpine`
  - Backend, from one container call:
    ```
    MSYS_NO_PATHCONV=1 docker run --rm --network ht-s4-net -v C:/dev/ht-s4-a/backend:/app -v ht-s4-venv:/venv -v ht-pipcache:/root/.cache/pip -w /app -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@ht-s4-pg:5432/cyber_threat_test_db -e APP_ENV=testing python:3.11-slim sh -c "python -m venv /venv && /venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt && /venv/bin/ruff check app tests evals && /venv/bin/ruff format app tests evals --check && /venv/bin/alembic -c app/db/alembic.ini upgrade head && /venv/bin/pytest tests/ -q"
    ```
    Expected: ruff clean, and pytest equal to the baseline plus the new authz tests, with 0 failed.
  - `python .github/scripts/check_threat_model.py docs/security/threat_model.md`: expected exit 0.
  - `python -m unittest discover -s .github/scripts`: expected OK.
- [ ] **Step 7: Commit** `docs(threat-model): T-AUTH-07 closed by the S4 real-verification suite`.
- [ ] **Step 8: The controller pushes and opens a draft PR** targeting `main`, titled `S4-A: authorization harness, real token verification, route table`. The body starts with `> Stacked on #225`. It includes the route counts, the mutation-check result from Task 2 Step 3, and the T-AUTH-07 move. Don't mark it ready.
