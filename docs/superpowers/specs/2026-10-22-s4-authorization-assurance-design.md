# S4: Authorization assurance — design

Date: 2026-10-22. Owner: Arlo Kharod. Roadmap: `docs/PRODUCT_VIABILITY_ROADMAP.md`, milestone S4. Stacked on #225 (S3 threat model). Input: `docs/security/threat_model.md`, the 14 rows listed for S4 in its OPEN RISK index.

## Intent

S4 replaces "the handlers look right" with tests that prove the API's authorization boundary, and fixes the gaps the S3 threat model scheduled here. Two claims must hold beyond doubt (Arlo's choice):

1. **One organization can't read or change another organization's data**, on every org-scoped route, including routes added later.
2. **Forged, expired, revoked or disabled logins are rejected**, by the real Firebase verification code, not a mock. Claim 1 rests on this: a cross-tenant test that runs under the autouse mock proves handler logic, not the boundary.

Everything else in S4 (roles, agent-token lifecycle, platform hardening) is required, but it's secondary to these two claims and is staged after them.

The portfolio bar is the roadmap's S4 résumé line ("route-enumerating authorization suite over [N] API endpoints ... real token verification; found and fixed [K] mis-scoped or unclassified routes ...") and its four interview questions.

## Goals

- A route-enumerating authorization suite under `backend/tests/authz/` that runs in the existing `Backend Tests` CI job (`pytest -v tests/`) with the autouse auth mock **disabled for that folder only**.
- Real token verification through `firebase_admin.auth.verify_id_token(..., check_revoked=True)` with a locally signed test key (decision 1).
- A committed route classification table covering every route in the app, with the suite failing on any unclassified or stale entry.
- Cross-tenant tests on every org-scoped route, member-vs-admin and admin-vs-owner tests on role-gated routes, and agent-token lifecycle tests on both agent routes.
- The fixes for each S4 row (T-TEN-05, T-TEN-07, T-TEN-10, T-AUTH-04, T-ENR-04, T-TOK-08, T-PLAT-01, T-PLAT-06, T-PLAT-09, T-UPL-09, T-DOM-09).
- Each S4 row in `threat_model.md` moves from OPEN to TEST (AUTH/TEN TEST rows carry the checker's `real-verification:` marker) or CONTROL, with evidence. Counts are updated in README.md, docs/README.md and the roadmap; the threat-model checker and the `.github/scripts` unittests pass.
- Close-out: roadmap S4 marked DONE in the S1/S2/S3 style with `[N]` (routes in the table) and `[K]` filled in. `[K]` counts **routes whose authorization behaviour changed** in S4 (a role check added or tightened, an org binding fixed, a verification requirement added), not threat-model rows closed. Three of the 14 rows (T-AUTH-07, T-TEN-12, T-TOK-07) close with tests alone; Obsidian `decisions.md` / `gotchas.md` / `todos.md` updated.

## Non-goals

- Ownership transfer, or granting the owner role through any route (unchanged: "Cannot assign owner role through this endpoint").
- Changing the global-admin bypass. Global admins (`users.role == "admin"`) reaching any org through `check_org_access` / `require_org_role` is by design (S3) and is tested as *allowed*, not removed.
- Merging the two role stores (legacy `users.org_id`/`org_role` vs `Membership`). S4 tests both paths and records any disagreement it finds; a data migration to unify them is out of scope unless a test proves a cross-tenant leak (then it goes to Arlo first, see Constraints).
- Enabling M365 in production. T-PLAT-16 stays ACCEPTED.
- DAST, ZAP, or the S5 rows.
- A Firebase Auth emulator job (rejected in decision 1).

## Anti-goals (a failure even if CI is green)

- **Any test in the suite running under the mock.** If `verify_id_token` is a `Mock` inside `tests/authz/`, claim 2 is gone. A guard test makes this fail loudly.
- **Silencing the enumerator by mislabelling a route.** Classifying a route `public` to make the suite pass. The dependency cross-check (below) makes this fail.
- **Accepting 500 as "denied".** A cross-tenant or role-denied request must return 401, 403 or 404. A 500 is a failure, even though nothing leaked.
- **Asserting status only on writes.** A cross-tenant write that returns 403 but changed org A's rows anyway is a leak. Write tests assert org A's data is unchanged.
- **Weakening an existing test to make room.** The existing suite keeps the mock and keeps passing unchanged, except where a fix (for example owner-only grants) changes the intended behaviour; those tests are updated to the new rule, not deleted.
- **Exploit detail in public text.** The repo is public. Commit messages, PR bodies and threat-model rows describe gaps at planning level.

## Constraints

- **Severe-finding stop.** If the suite finds a cross-tenant read or write, an auth bypass, or a leaked credential that S3 didn't already record, stop and tell Arlo before writing it anywhere (code comment, commit, PR, threat model). This is the S3 rule, unchanged. Escalation: halt the stage, commit and push nothing that reveals the finding (a failing test stays local and uncommitted), and report it to Arlo in the session chat only; resume once Arlo decides (fix first, as with #224, or schedule it). Rows S3 already recorded are *not* new findings: T-TEN-10 (the analytics route accepts a client-supplied org) and T-TEN-05 are known, judged not severe, and fixed in their stages without stopping.
- Gate per stage: ruff; `alembic upgrade head` before pytest; backend tests in `python:3.11-slim` with a venv volume, a throwaway Postgres on its own Docker network, `DATABASE_URL` and `APP_ENV=testing` (`MSYS_NO_PATHCONV=1` for `docker run -v C:/...`); frontend lint and tests if `firebase.json` or the frontend changes; `python .github/scripts/check_threat_model.py docs/security/threat_model.md`; `python -m unittest discover -s .github/scripts`.
- Five stages, one PR and one session each, stacked. Every PR targets `main` as a draft with a "Stacked on #…" banner (CI only runs on PRs to `main`), and is rebased with `--onto` after the lower PR squash-merges.
- No new runtime dependency for the test harness beyond what `requirements-dev.txt` can carry; `cryptography` and `pyjwt` are already in the tree via firebase-admin.
- Never merge, deploy, mark PRs ready, push tags, change repo settings, or touch IAM.

## Decisions

### 1. Real token verification: a locally signed test key (decided)

**Why not the emulator.** In firebase-admin 6.4.0, when `FIREBASE_AUTH_EMULATOR_HOST` is set, `_JWTVerifier.verify` takes the token's payload as already verified (`firebase_admin/_token_gen.py`, the `if emulated: verified_claims = payload` branch) and skips the `kid` and `alg` checks. The signature and `exp` are never checked. An emulator suite could not prove that a forged or expired token is rejected, which is the core of T-AUTH-07. It would also add a Java/Node service to CI.

**What the suite does instead:**
- Each test session generates an RSA key pair and a self-signed X.509 certificate with a fixed `kid`.
- A helper mints Firebase-shaped ID tokens: header `{alg: RS256, kid}`; claims `aud = <test project id>`, `iss = https://securetoken.google.com/<test project id>`, `sub`/`uid`, `iat`, `exp`, `auth_time`, `email`, `email_verified`, `firebase.sign_in_provider`. Every claim can be overridden per test.
- The SDK's certificate fetch (`ID_TOKEN_CERT_URI`) is answered with `{kid: cert_pem}` **at the HTTP-transport layer**, so `google.oauth2.id_token.verify_token` runs for real: signature, `exp` (with the app's 10 s `clock_skew_seconds`), `aud`, `iss`.
- `check_revoked=True` makes the SDK look up the user through the Identity Toolkit API. That call is answered at the HTTP layer by a fake that holds, per uid, a `disabled` flag and a `validSince` / tokens-valid-after time. Tests revoke or disable a user by changing the fake; the SDK's own `_check_jwt_revoked_or_disabled` decides.
- The suite initialises a real `firebase_admin` app (named or default, the builder's call) with the test project id and a credential that never contacts Google (for example a `google.auth` credential whose token refresh is a no-op, so the Identity Toolkit call carries a dummy bearer to the fake). The existing `_mock_firebase_init` autouse fixture stays as is; the suite's own fixture provides the app.
- **What may be patched (decided):** only the network edge: the `requests` session or transport adapter the SDK uses for the cert fetch and for Identity Toolkit (mounting a test adapter, or a narrow patch that swaps the session's transport). Nothing in `firebase_admin.auth`, `_token_gen`, `_auth_client`, `google.oauth2.id_token` or `google.auth.jwt` may be patched. A test asserts the cert fake was actually hit, so a cached real cert can't silently stand in.

**Claim-2 tests (T-AUTH-07).** Each against at least one protected human route, each expecting 401 (never 500):
- a token signed by a different key with the same `kid`;
- an expired token, just past the 10 s skew allowance, using a frozen or injected clock (no `sleep`);
- a token for the wrong `aud`, and for the wrong `iss`;
- an `HS256` token, and an `alg: none` token;
- a token whose `iat` predates the user's revocation time;
- a token for a disabled user;
- a missing or malformed `Authorization` header;
- an agent token (`ht_<prefix>_<secret>`) on a human route, and a valid Firebase token on an agent route.

### 2. How the autouse mock is disabled (decided)

- `backend/tests/authz/conftest.py` redefines a fixture named `_mock_firebase_verify` that does nothing. Pytest's fixture override by name in a subdirectory replaces the parent's autouse fixture for that folder only; every other test keeps the mock.
- **Guard test:** inside the suite, assert that `firebase_admin.auth.verify_id_token` is the SDK's real function (not a `unittest.mock` object). It runs first and fails loudly if a future conftest change brings the mock back.
- The suite never uses the shared `client` fixture (whose `Bearer fake-test-token` only works under the mock). It uses its own clients that carry minted tokens.

### 3. The route classification table (decided)

- **Location and format:** a Python module, `backend/tests/authz/route_table.py`, so it is type-checked, linted, and importable without a parser. One entry per `(method, path)`:
  - `cls`: one of `public`, `authenticated-global`, `organization-scoped`, `agent`, `administrator`;
  - `org_from` (org-scoped only): `path` (an `org_id` path parameter), `caller` (resolved from the caller, e.g. `get_current_org`), or `resource` (resolved through a resource id that belongs to an org);
  - `min_role`: the minimum role the route intends (`viewer`/`member`/`admin` globally, or `member`/`admin`/`owner` in the org);
  - `flag` (optional): a feature flag the route depends on, e.g. `ENABLE_M365_INTEGRATION`;
  - `note`: one line.
- **Class meanings:**
  - `public`: no authentication (landing-page stats, data-status, health, the M365 OAuth callback if it is state-token protected, docs/openapi if mounted).
  - `authenticated-global`: any signed-in user, no org data (e.g. `/auth/me`, global vulnerability and threat feeds behind `require_role("viewer")`, onboarding org creation).
  - `organization-scoped`: reads or writes data owned by one org.
  - `agent`: agent bearer token only (`get_agent_from_token`).
  - `administrator`: global admin only (`require_role("admin")`, e.g. ingestion triggers).
- **Enumeration:** walk every route in `app.routes` (API routes and any non-API routes such as `/docs` and `/openapi.json`); each alias of a doubled path (`/orgs/...` and `/organizations/...`) is its own entry; `HEAD`/`OPTIONS` that FastAPI adds implicitly are ignored. The suite fails on: a route missing from the table; a table entry with no matching route (stale); a duplicate entry.
- **Dependency cross-check:** for each route, inspect its resolved dependency tree (including router-level `dependencies=`):
  - `public` → no dependency on `get_current_user` or `get_agent_from_token`;
  - `agent` → depends on `get_agent_from_token` and not on `get_current_user`;
  - every other class → depends on `get_current_user`;
  - `administrator` → depends on `require_role("admin")`.
  Org scoping enforced inside a handler body (`check_org_access`) is invisible to this check and is covered by the behaviour tests in decision 4.
- **Feature-flagged routes:** the M365 routes are always registered (`v1/__init__.py` includes `integrations.router` unconditionally) and check `settings.ENABLE_M365_INTEGRATION` at request time, returning 503 when it is off (`integrations.py`, the flag check near L58). The flag is off by default, so in CI and in production. They are classified by their real class plus `flag`. Their behaviour tests force the flag on (settings override) so they exercise tenancy rather than the 503 short-circuit. T-PLAT-16 stays ACCEPTED, but the routes are classified and tested.
- **Counted:** the suite prints a per-class route count; the stage-A PR body records the totals, and the close-out fills `[N]`.

### 4. Cross-tenant tests (claim 1)

- **Role stores (decided).** Today each check reads one store: `get_current_org`, `check_org_access` and `require_org_role` read the legacy `users.org_id`/`org_role`; `require_same_org_membership` / `require_membership_role` read `Membership`, falling back to the legacy fields when no membership row exists. S4 does not change which store each existing check reads. New role checks added in S4 (T-TEN-05, T-TEN-07) use the same mechanism as the route they're added to, so a route never mixes stores. The fixture world's normal users are consistent in both stores. It also includes **one deliberately split user**: legacy `org_id` = A, active `Membership` only in B. The sweep runs that user against both orgs' routes and records, per route, which org it reaches. Reaching a route of an org where it holds neither a legacy nor a membership claim is a leak (severe-finding stop). Reaching one of its two claimed orgs is the known T-TEN-12 drift; it's recorded in the stage-B PR body and the threat-model row, not fixed in S4.
- Fixture world: two orgs, A and B. Each has an owner, an admin, a member and (if the role exists) a viewer, created through both role stores consistently (a `Membership` row and the legacy `users.org_id`/`org_role`). Plus a global admin with no org and a signed-in user with no org. Org A owns at least one of every resource kind an org-scoped route touches (domains, vendors, uploads, inventory assets and scan runs, assessments, members, invites, agents, AI summaries, integration credentials if needed).
- For every `organization-scoped` route, call it as each of B's roles **targeting A's resources** (A's `org_id` in the path, or A's resource id for `resource` routes). Expect 403 or 404, never 2xx, never 500. For `caller` routes, confirm a B caller only ever sees B's data.
- Writes (POST/PUT/PATCH/DELETE): after the denied call, assert org A's affected rows are unchanged.
- Global admin: assert it is allowed on the routes where the bypass is by design, so the boundary is documented by tests rather than assumed.
- Responses on denial must not contain org A's identifiers or data in the body.
- Parametrised from the table: an org-scoped route with no cross-tenant case fails the suite (the builder may express per-route request builders in the table module or alongside it).
- **403 vs 404:** both count as denial for the acceptance criteria. The suite records which one each route returns; S4 does not normalise them (the interview question gets a written answer in the stage-B PR body).
- **T-TEN-10:** the analytics event route binds events to the caller's org; the cross-tenant write test proves it.
- **T-TEN-12 closes** when every org-scoped route has a passing cross-tenant case under real verification.

### 5. Role rules

- **T-TEN-07, owner-only member management (Arlo's decision):** admins manage plain members only; anything that touches an admin or an owner requires the owner role. Concretely, owner-only: inviting as admin; promoting to admin; demoting an admin; removing an admin; any change to or removal of an owner. Admins keep: inviting members, changing a member's role below admin, listing and revoking invites (the builder decides whether revoking a pending *admin* invite is owner-only, and records the call), and removing plain members. Last-owner protections stay. Global admins don't bypass member routes today (`require_membership_role` checks `Membership`); that stays. The docstrings are corrected to match.
- **T-TEN-05 (rule decided; list derived in stage C):** a route is *destructive* if it deletes org data, disconnects an integration, revokes an org credential (agent, invite), or deletes or exports the org (data lifecycle). Destructive org-scoped routes require org admin or higher. Creating and editing (adding a domain, uploading a file or CSV, submitting an assessment, editing the vendor stack) stays member-level. Stage C derives the concrete list from the table by this rule, records it in the plan and the PR body, and sets `min_role` to match. The suite tests member-denied and admin-allowed on each.
- **T-AUTH-04 (current state):** S0 already gates the link-by-email path in `get_current_user` (`auth.py` ~L73: an existing unbound user is linked only when `email_verified` is true, else 403). What remains is the two other paths: **auto-create** of a new local user (currently no `email_verified` check) and **invite acceptance** (`members.py::accept_invite`). Both refuse an unverified token with 403 (matching the S0 link-path response), never 401 (the token itself is valid) and never 500. Existing `test_auth.py` / members tests that auto-create or accept with the mock's `FAKE_FIREBASE_TOKEN` (which has no `email_verified`) are updated by adding `email_verified: True` to that fake token; that's a fixture change, not a weakened test. The frontend must already surface the unverified-email state; if it doesn't, a minimal message is in scope.

### 6. Agent-token lifecycle (stage D)

- **T-TOK-07:** end-to-end tests on both agent routes with real `get_agent_from_token` (no dependency override): a valid token is accepted; a revoked token, an expired token, and a rotated predecessor past its grace window are each rejected with 401. Grace is tested with an injected clock, not sleeping.
- **T-ENR-04:** rotation acts only on active rows, and never moves `revoked_at` later or revives a revoked or expired enrollment.
- **T-TOK-08:** revoking an agent revokes its whole rotation chain (or the successor is otherwise unusable). Test: rotate, revoke by the original id, then the successor's token gets 401.
- **Replay:** a replayed upload is rejected (existing replay control, now tested end to end).

### 7. Platform (stage E)

- **T-PLAT-01:** security-headers middleware on the API (HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` or CSP `frame-ancestors 'none'`, `Referrer-Policy`, a restrictive CSP for API responses); a `headers` block in `firebase.json` for the SPA, with a CSP the frontend actually works under. Verify it against the built app (`npm run build`, then serve `dist/` locally with the same headers and exercise sign-in and the main pages with no CSP console violations), and again on the PR's Firebase deploy-preview channel. Tests assert the headers on API responses.
- **T-PLAT-06:** an app-wide request-body size limit enforced before the body is read, with a pre-read size check on file uploads, returning 413. The agent upload route's limit fits the largest legitimate scan: derive it from the upload schema's existing per-list caps (worst-case serialized size of a maximal payload, plus headroom), and record the arithmetic in the PR body. Other JSON routes get a smaller app-wide default; file-upload routes keep their own documented cap. Tests send an oversize body and expect 413, not 500 or memory growth.
- **T-PLAT-09:** `/health` runs a cheap DB query and returns 503 when the DB is unreachable. Render's health check keeps working.
- **T-UPL-09:** the agent refuses a non-HTTPS `--server` URL (an explicit, documented opt-out for `http://localhost` development is the builder's call); Go test included. HSTS comes from T-PLAT-01.
- **T-DOM-09:** regression tests that fail if the domain-check HTTP client starts following redirects (`follow_redirects=False` pinned on the real client) or if the redirect default-port rule is removed (a redirect to a non-default port is refused).

## Stages

| Stage | Scope | Closes |
|---|---|---|
| **A** | Harness: real verification, mock override and guard, token minting, fake cert and Identity Toolkit endpoints, route enumerator, full classification table, dependency cross-check, claim-2 tests | T-AUTH-07 |
| **B** | Fixture world, cross-tenant sweep over every org-scoped route, T-TEN-10 fix | T-TEN-12, T-TEN-10 |
| **C** | Role tests and fixes | T-TEN-05, T-TEN-07, T-AUTH-04 |
| **D** | Agent-token lifecycle tests and fixes | T-TOK-07, T-ENR-04, T-TOK-08 |
| **E** | Headers + `firebase.json`, body limit, DB `/health`, agent HTTPS-only, egress regression tests | T-PLAT-01, T-PLAT-06, T-PLAT-09, T-UPL-09, T-DOM-09 |

Stage A ships the whole table, so every later stage starts from zero unclassified routes. Each stage updates the threat-model rows it closes, the counts, and the checker run in the same PR. The roadmap is marked DONE only at the end of stage E.

## Acceptance (from the roadmap, unchanged)

Unclassified routes: 0. Cross-tenant leaks: 0. Routes returning 500 on a denied request: 0. The suite runs with the autouse auth mock disabled. The classification table is committed and counted. All 14 S4 rows are TEST or CONTROL.

## Left to the builder

- File layout inside `tests/authz/` beyond `conftest.py` and `route_table.py`.
- The exact HTTP-layer hook used to answer the cert fetch and the Identity Toolkit lookup, provided the SDK's own verification and revocation logic runs unpatched.
- How per-route request builders for the cross-tenant sweep are expressed.
- Header values beyond those listed, the body-size limit numbers, and the `/health` query, within the rules above.
