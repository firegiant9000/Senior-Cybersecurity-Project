# S4 stage E: platform hardening (T-PLAT-01, T-PLAT-06, T-PLAT-09, T-UPL-09, T-DOM-09) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last five S4 rows (spec decision 7) and mark S4 done:
- the API sends security headers on every response, including errors, preflights and the docs pages, and Firebase Hosting sends a CSP the SPA works under (T-PLAT-01);
- every request body is capped before it is read, with 413 on overflow, a per-route limit for the agent upload and the file routes, and a pre-read size check on uploaded files (T-PLAT-06);
- `/health` checks the database and returns 503 when it can't reach it (T-PLAT-09);
- the Go agent refuses a non-HTTPS `--server` URL and doesn't follow redirects (T-UPL-09);
- regression tests pin the domain-check client's `follow_redirects=False` and the redirect port rule (T-DOM-09).

**Architecture:**
- **Two pure-ASGI middlewares** in `app/core/`: `SecurityHeadersMiddleware` (outermost) and `BodySizeLimitMiddleware` (**innermost**, inside `RequestContextMiddleware`). They're pure ASGI, not `BaseHTTPMiddleware`, so they don't buffer bodies or wrap tasks.
- **Unhandled-exception responses.** These are produced by Starlette's `ServerErrorMiddleware`, which sits outside every user middleware. They get their headers from an `Exception` handler that builds the same plain 500 and applies the same headers.
- **The body cap** has two parts. It refuses a declared `Content-Length` over the limit without reading, and it counts the bytes `receive` delivers, raising `HTTPException(413)` once they pass the limit. FastAPI re-raises an `HTTPException` raised while it reads a body (`fastapi/routing.py` L406).
  - **Why innermost.** `SlowAPIMiddleware` and `RequestContextMiddleware` are `BaseHTTPMiddleware`. Their `receive` runs inside an anyio task group, so an exception raised in a `receive` wrapper outside them comes back to FastAPI as an `ExceptionGroup`: a 400 on body params, and a 500 on the agent route (pre-flight review, round 1).
  - Innermost, the wrapper raises in its own frame, after the downstream `receive` has returned. The 413 then goes out through the normal exception handler, with X-Request-ID, CORS and security headers.
- **Revised after review, rounds 1 and 2 (supersedes the 80 MiB, 8 MiB, "large upload", one-slot and semaphore wording below, including the Interfaces block and the Task 3 test list).** The agent list caps are now 20,000 software, 5,000 services and 5,000 ports, so the worst-case body is 19,311,014 bytes (18.4 MiB) and `MAX_AGENT_UPLOAD_BYTES` is 24 MiB (30 % headroom). `AGENT_LARGE_UPLOAD_BYTES`, `AGENT_UPLOAD_CONCURRENCY` and the count cap (`AGENT_MAX_CONCURRENT_UPLOADS`, tried in round 1) are gone. One gate admits every agent upload, at any size, before its body is read:
  - **Weight is the declared Content-Length.** A body without a valid one (chunked) is admitted as a maximal upload (`MAX_AGENT_UPLOAD_BYTES`), so while it runs it holds 24 MiB of the process budget and its org's whole share: other uploads from that org wait, and uploads over 8 MiB from other orgs wait; round 3 replaced an earlier 411. Both the current agent and `agent-v0.1.0` send a Content-Length (`bytes.NewReader` sets `ContentLength`), so they are unaffected. The middleware still caps the streamed bytes (413 over MAX).
  - **A byte budget, weighted by the declared length:** `AGENT_UPLOAD_BUDGET_BYTES` (32 MiB) process-wide and `AGENT_UPLOAD_ORG_BUDGET_BYTES` (24 MiB) per org, plus one in flight per enrollment (a duplicate is an immediate 503). Settings validation requires both budgets to be at least `MAX_AGENT_UPLOAD_BYTES`, so one maximal upload is always admissible.
  - **A bounded wait:** a request that does not fit waits up to `AGENT_UPLOAD_WAIT_SECONDS` (10) for room, then gets 503 `"Agent upload busy; retry shortly"` with `Retry-After: 5`. Every exit path releases the reservation and wakes waiters.
  - The token check's transaction is committed before the wait and the read, so neither holds a pooled DB connection. The body is streamed into a local buffer, not cached on the Request, and may not outrun its declared length (413).
- **The agent upload reads its body after the token check, under a slot and a read deadline.** FastAPI reads declared body params before it solves dependencies, so today an unauthenticated caller can make the server read and parse a body of any size on that route.
  - The payload becomes a dependency that depends on `get_agent_from_token`, and then on the upload slot (503 when it can't be taken, without reading).
  - The body read runs under `asyncio.timeout(AGENT_UPLOAD_READ_TIMEOUT_SECONDS)` (60 s), so a trickled body can't hold the slot indefinitely.
  - The body allowance is only read for a valid agent, and the number of bodies in flight is bounded.
  - **This isn't a CPU bound.** pydantic-core holds the GIL while it validates, and the rest of the handler is synchronous. A maximal upload still stalls the event loop for around a second (measured: 0.63 s stall on a 70 MB parse, round-2 review). The bounds are the slot and the list-cap follow-up.
- **`/health`** runs `SELECT 1` on a dedicated one-connection engine with a 2 s timeout. The result is cached for 2 s and shared by concurrent callers, so flooding `/health` can't exhaust the app's pool or make it report 503. The 503 test points the engine dependency at an unreachable engine; the shared test DB is never stopped.
- **The Go agent** validates the URL in `upload.New`, and its `http.Client` refuses every redirect.

**Tech Stack:** Python 3.11, FastAPI 0.133 / Starlette, SQLAlchemy 2 async + asyncpg, Postgres 15, pytest 9 + pytest-asyncio, httpx `ASGITransport`; Go 1.27 (stdlib only); Firebase Hosting (`firebase.json`); `.github/scripts` unittest.

**Spec:** `docs/superpowers/specs/2026-10-22-s4-authorization-assurance-design.md`: decision 7 (L132–138) in full; Anti-goals (L35–42); Constraints (L44–50); Stages (L140–150; the roadmap is marked DONE only at the end of stage E); Left to the builder (L161: header values, body-size numbers, `/health` query).

## Global Constraints

- **Git.**
  - Worktree `C:/dev/ht-s4-e`, branch `feat/s4-platform`, stacked on `feat/s4-agent-tokens` (#229).
  - Commit as `git -C C:/dev/ht-s4-e -c user.name="Arlo Kharod" -c user.email="42082766+firegiant9000@users.noreply.github.com" commit -F <msgfile>`, with the message file in the session scratchpad.
  - No Claude attribution. One shell command per Bash call.
- **No new runtime or dev dependency** (spec Constraints). The Go agent stays stdlib-only (`agent/go.mod` header). No Playwright: the browser CSP check is owner-run (Task 5).
- **Status codes.** An oversize body is exactly **413**, with `{"detail": "Request body too large"}`; a file over the upload cap keeps today's 413 detail, `"File exceeds maximum size of 10 MB"`. A 400, 422 or 500 for an oversize body fails the test. An unreachable DB on `/health` is exactly **503**.
- **No error text in responses.** The 503 body and the 500 body carry no exception message, host or driver text (T-PLAT-07 is S5's, but this stage must not add a leak). Health logs record only the exception class name.
- **Real verification in `tests/authz/`.** The agent-route tests in this stage go in `tests/authz/tenancy/` and use stage D's `_agents.py` helpers (`issue_agent`, `authz_client`, `scan_payload`, `snapshot_org`). Never use `app.dependency_overrides` or a patch on `get_agent_from_token` there. The only patches allowed are `monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", …)`, occupying or resetting the upload gate (`_reset_agent_upload_slots`, `_agent_gate().acquire/release`), and the stage-D clock.
- **Settings are read at request time** by the body-limit lookup, so tests can lower a limit with `monkeypatch.setattr(settings, …)` instead of sending megabytes.
- **Existing tests are updated to the new rule, never deleted** (spec Anti-goals). A changed test keeps its name, or its rename goes in the commit body. Task 8 lists them.
- **Severe-finding stop.** If anything severe that S3 didn't record turns up (cross-tenant access, an auth bypass, a leaked credential): stop, leave the test uncommitted, and report to the controller in chat only. These are known and not a stop: the five stage-E rows, the T-TEN-12 drift, the assessments 500, and the agent route reading its body before authentication (it's part of T-PLAT-06, fixed in Task 3).
- **Public repo.** Commit messages, notes and the PR body describe the gaps at planning level only.
- **Lint.** From `backend/`, run `ruff check app tests evals` and `ruff format app tests evals --check`. For Go, run `go vet ./...`, `gofmt -l .` (expect no output) and `go test ./...`, each in `golang:1.27` (Task 6).
- **CodeQL `verify=False` alerts are per call shape** (gotchas, "S3 threat model"). Task 1's tests must not add a new `httpx.AsyncClient(..., verify=False)` call. They reuse the real factory.
- **Mutation checks are owner-run.** The auto-mode classifier blocks temporary security-weakening edits, including TDD red runs that delete a guard. Task 7 hands Arlo the steps. Accept a collection-level red where a guard already exists.

## Review Focus

1. **Firebase Auth's other calls under the SPA CSP.** These are the token refresh, sign-up, password reset and the email-verification refresh (`user.reload()`, then `getIdToken(true)`, from stage C), not just sign-in. Each one goes to `identitytoolkit.googleapis.com` or `securetoken.googleapis.com`. If either is missing, sign-in works, but the session dies an hour later. Pinned by `test_spa_csp_allows_firebase_auth_endpoints` (Task 5), and by the owner preview check, which waits for a token refresh.
2. **An org logo hosted anywhere.** `OrgProfilePage.tsx` L777 previews `logo_url`, an arbitrary `https://` URL. A tight `img-src` breaks that silently: `onError` just hides the image. Pinned by `test_spa_csp_allows_org_logo_images` (Task 5).
3. **A chunked upload to a file route.** Browsers send `Content-Length` for `FormData`, but `curl -T` and some clients stream without it. The streaming cap must apply on the file limit as well as on the default. Pinned by `test_chunked_body_over_limit_is_413_and_read_stops[file-route]` (Task 3).
4. **A DB that hangs rather than refuses.** Render's health check must get a 503 in about 2 s, not hang until the platform's own timeout. Pinned by `test_database_reachable_times_out` (Task 2).
5. **An operator running the agent against `http://localhost:8000`.** This is the docker-compose dev stack in `agent/README.md`. It must keep working without a flag, and `HT_SERVER` with a trailing slash must still be accepted. Pinned by `TestNewAllowsHTTPSAndLoopbackHTTP` (Task 6).

## Decisions made in this plan

### T-PLAT-01: API headers
- **Values**, on every HTTP response:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`;
  - `X-Content-Type-Options: nosniff`;
  - `X-Frame-Options: DENY`;
  - `Referrer-Policy: no-referrer`;
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.
  
  No `preload`: the API host is a `*.onrender.com` subdomain, and preload needs the apex.
- **HSTS is sent in every environment.** Browsers ignore HSTS received over plain HTTP (RFC 6797 §8.1), so sending it to `http://localhost` in dev is a no-op. Gating it on `APP_ENV` would add a branch that the tests (`APP_ENV=testing`) could never exercise. Render terminates TLS and forwards the app's headers, so clients receive it over HTTPS. HSTS protects browsers only. The Go agent's protection is Task 6.
- **The docs pages get their own CSP.** These are `docs_url`, `redoc_url` and `swagger_ui_oauth2_redirect_url`, read from the app at startup rather than hard-coded. T-PLAT-08 keeps them public in production. FastAPI's Swagger UI and ReDoc pages use an inline bootstrap script, plus assets from `cdn.jsdelivr.net`, Google Fonts (ReDoc), `fastapi.tiangolo.com` (favicon) and `blob:` workers (ReDoc). Their CSP is:

  ```
  default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/ https://cdn.jsdelivr.net/npm/redoc@2/; style-src 'unsafe-inline' https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/ https://cdn.jsdelivr.net/npm/redoc@2/ https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; connect-src 'self'; worker-src blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
  ```

  - **The jsdelivr sources are path-restricted** to `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/` and `https://cdn.jsdelivr.net/npm/redoc@2/`, in both `script-src` and `style-src`, instead of the whole CDN. That's because a user may paste a bearer token into Swagger's Authorize box.
  - `'unsafe-inline'` is acceptable there: the pages render only the public schema, on the API origin.
  - **Residual:** FastAPI loads those packages by major version without SRI, so the docs page trusts that CDN path. T-PLAT-08 accepts public docs. Recorded in the PR.
  - A structural test parses the served HTML and checks that every external `src`/`href` URL matches an allowed source (origin plus path prefix), so a FastAPI bump that moves the CDN path fails CI.
- **Headers are added only if absent,** so a route can set its own (none does today).
- **The 500 path.** `fastapi_app.add_exception_handler(Exception, _internal_error)` returns `PlainTextResponse("Internal Server Error", status_code=500)`, the same body Starlette sends today, with the security headers. `ServerErrorMiddleware` still re-raises afterwards, so logging and Sentry are unchanged. CORS headers aren't on 500s, which is today's behaviour.
- **Middleware order** (outermost first): `SecurityHeadersMiddleware` → `CORSMiddleware` → `SlowAPIMiddleware` → `RequestContextMiddleware` → `BodySizeLimitMiddleware` → routes.
  - `add_middleware` prepends, so in `create_app`, `BodySizeLimitMiddleware` is added **first** (before `RequestContextMiddleware`) and `SecurityHeadersMiddleware` **last**.
  - A 413 from the body limit therefore carries X-Request-ID, CORS and security headers, and a preflight answered by CORS carries the security headers.
  - **Don't move the body limit outward**: see Architecture, "Why innermost".

### T-PLAT-01: SPA headers (`firebase.json`)
- One `headers` entry for `"source": "**"`, with these headers:
  - `X-Content-Type-Options: nosniff`;
  - `X-Frame-Options: DENY`;
  - `Referrer-Policy: strict-origin-when-cross-origin`;
  - `Content-Security-Policy` as below.
  
  **No HSTS:** Firebase Hosting already sends it on `*.web.app`. The owner check confirms it with `curl -sI`.
- **The CSP**, with a justification for each origin:

  | Directive | Sources | Why |
  |---|---|---|
  | `default-src` | `'self'` | fallback |
  | `script-src` | `'self'` | Vite emits one external module script (`index.html` L14); there's no inline script and no `eval` |
  | `style-src` | `'self' https://fonts.googleapis.com` | Vite's CSS file; the Inter stylesheet (`index.html` L10). React `style={}` props go through the CSSOM, which CSP doesn't block |
  | `font-src` | `'self' https://fonts.gstatic.com` | the Inter font files |
  | `img-src` | `'self' data: https:` | `/logo.png`; data URIs from chart libraries; **org logos at any `https:` URL** (Review Focus 2). Images can't run script. The residual is that an org admin's logo host sees viewers' IPs, which is accepted |
  | `connect-src` | `'self' https://hacker-tracker-backend.onrender.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://*.ingest.sentry.io https://*.ingest.us.sentry.io` | `/states-10m.json` (map); the API (`frontend/.env.production`); Firebase Auth REST and token refresh; Sentry ingest. The DSN is a CI secret, so both regional ingest hosts are listed. The owner check confirms which one is used |
  | `frame-src` | `https://hacker-tracker-75f91.firebaseapp.com` | Firebase Auth's helper iframe on the project's auth domain. Email/password sign-in may never load it. The owner check records whether it does; if it doesn't, a follow-up removes the source. **Fallback if the preview shows `apis.google.com` or iframe violations:** `getAuth()` wires in `browserPopupRedirectResolver`, so switch `firebase.ts` to `initializeAuth(app, {persistence: [indexedDBLocalPersistence, browserLocalPersistence]})` with no resolver and drop `frame-src`, rather than widening `script-src` |
  | `object-src` | `'none'` | |
  | `base-uri` | `'self'` | |
  | `form-action` | `'self'` | |
  | `frame-ancestors` | `'none'` | clickjacking (T-PLAT-01) |
  | `upgrade-insecure-requests` | | |

  Not listed, deliberately: `apis.google.com` and `accounts.google.com`, which are only needed for popup or redirect sign-in. The app uses email/password only (`AuthContext.tsx` L117). The M365 consent is a top-level navigation (`IntegrationsPage.tsx` L85), which CSP doesn't restrict.
- **Enforced, not report-only:** report-only wouldn't close T-PLAT-01. The safety net is the owner's preview-channel check (Task 5), which runs before Arlo merges.
- **Test home.** The checker accepts TEST evidence only from `test_*.py`, `*_test.py` or `*_test.go` files. A Vitest file can't be evidence, so the `firebase.json` test is a unittest, `.github/scripts/test_firebase_hosting_headers.py`, which runs in `security.yml` with the other script tests.
- **Who runs the browser check: Arlo.** The repo has no Playwright, sign-in needs a real Firebase account, and the preview URL appears only after the controller pushes. The implementer builds the app and runs the unittest. Arlo runs the local `firebase serve` check and the preview-channel check from the PR checklist.

### T-PLAT-06: body limit
- **Limits:**

  | Route | Limit | Setting |
  |---|---|---|
  | `POST /api/v1/inventory/scans` (agent upload) | 24 MiB = 25,165,824 bytes | `MAX_AGENT_UPLOAD_BYTES` (new) |
  | the 5 multipart routes: `…/uploads`, `…/vendors/import`, `…/vendors/import/preview`, `…/inventory/uploads/csv/preview`, `…/inventory/uploads/csv/import` (all under `/api/v1/organizations/{org_id}`) | `MAX_UPLOAD_SIZE_BYTES` + 64 KiB multipart overhead = 10,551,296 bytes | `MAX_UPLOAD_SIZE_BYTES` (existing, 10 MiB) |
  | everything else | 1 MiB = 1,048,576 bytes | `MAX_JSON_BODY_BYTES` (new) |

  The largest other JSON body is an assessment submission or an org profile edit, both well under 100 KB. The full suite (Task 3 Step 5) is the check that nothing legitimate exceeds 1 MiB.
- **Agent arithmetic.** These are the worst-case compact-JSON bytes of a maximal payload, with every string at its `max_length` in ASCII, from `app/schemas/agent_scan.py`. The Go agent sends compact JSON from `json.Marshal` (`agent/internal/upload/client.go` L62).
  - Per item, the keys and punctuation, plus the strings at their caps:
    - software: `{"vendor":"…","product":"…","version":"…"}` = 39 + 255 × 3 = **804** bytes;
    - service: `{"name":"…","state":"…"}` = 22 + 255 + 64 = **341**;
    - port: `{"port":65535,"protocol":"tcp","process":"…"}` = 44 + 255 = **299**.
  - The lists hold 20,000 software, 5,000 services and 5,000 ports, with one comma fewer than items between them:
    - software 16,099,999;
    - services 1,709,999;
    - ports 1,499,999.
  - The top level and the host come to **1,017** bytes: the top-level keys, `scan_id` 64, `nonce` 128, `scanner_version` 32, `schema_version` `"1.0"`, three `[]`, and a host with every field at its cap (677).
  - **Total: 19,311,014 bytes (18.4 MiB).** The limit is 24 MiB, 30 % headroom.
  
  The test `test_maximal_agent_payload_fits_limit` builds this payload from the schema's own caps. It asserts the byte count, that it validates, and that it fits, so raising a cap without the limit fails CI.
- **The headroom doesn't cover a maximal payload made entirely of non-ASCII or escaped characters.** Go escapes `<`, `>` and `&` as 6 bytes, and non-ASCII is 2–4 bytes. Real package metadata is overwhelmingly ASCII, and 150,000 entries all at maximum length aren't a legitimate scan. Such a payload gets 413, which is acceptable.
- **Residual (as first measured at the old 80 MiB limit; the caps are now lower, see the revision above).**
  - **Measured in the pre-flight review:** `model_validate_json` alone on the maximal 72 MB payload takes peak RSS from 168 to 327 MiB. On top of that come the body bytes, `payload_hash` (`model_dump` plus `json.dumps`), the row building and the ORM objects.
  - **A valid agent token isn't a real barrier.** Any self-registered account can create an org (`onboarding.py` L25) and enroll an agent (`agents.py` L45).
  - **The 12/minute rate limit doesn't help either.** slowapi checks decorated routes inside the endpoint wrapper, after the payload dependency has already read and parsed the body.
  - **What this stage adds:**
    - admission by declared Content-Length for every agent body: a 32 MiB process-wide byte budget, a 24 MiB per-org share and one in flight per enrollment. A request that does not fit waits up to 10 s, then gets 503 `"Agent upload busy; retry shortly"` with `Retry-After: 5`, and the body isn't read;
    - a 60 s read deadline (`AGENT_UPLOAD_READ_TIMEOUT_SECONDS`). On expiry the response is 408 `"Agent upload timed out"`, and the slot is released.
    
    So the bodies in memory at once are bounded by the byte budget, and a slow-loris holds the slot for at most 60 s per request. The loop still stalls while a large payload is parsed (Architecture).
  - **Residual: one org can make other orgs wait up to 10 s,** and the Go agent doesn't retry a 503 today, so an upload that loses the wait is lost until its next run. A bounded retry that honours `Retry-After` ships with the next agent release.
  - **The per-list caps were lowered** (20,000 / 5,000 / 5,000) on the owner's decision at review. The Go agent applies no caps of its own, so no agent change was needed.
- **The agent upload authenticates before it reads the body.** `upload_agent_scan`'s `payload` becomes `Depends(read_agent_payload)`.
  - `read_agent_payload` depends on `agent_upload_slot`, a yield dependency that depends on `get_agent_from_token` (which FastAPI caches per request, so it's the same call the handler's `enrollment` uses), requires Content-Length, ends the session's transaction, takes a place in the byte-budget gate (waiting up to `AGENT_UPLOAD_WAIT_SECONDS`), and releases it at the end.
  - It streams `request.stream()` into a local buffer under the read deadline (the middleware caps the size), and returns `AgentScanPayload.model_validate_json(body)`.
  - **A client disconnect mid-read** (`starlette.requests.ClientDisconnect`) becomes `HTTPException(400, "Client disconnected")`. Without this, it would be an unhandled 500 and a Sentry event, because a dependency has no FastAPI body-read wrapper around it.
  - The order is: token, then slot, then read. The two sub-dependencies are declared in that order; FastAPI solves them in parameter order. An unauthenticated request never takes a slot.
  - A `ValidationError` becomes `RequestValidationError` with each error's `loc` prefixed by `"body"` (from `exc.errors(include_url=False)`), so the 422 body keeps FastAPI's shape.
  - The route loses its generated OpenAPI request-body schema. `openapi_extra={"requestBody": {"required": True, "description": "AgentScanPayload: see backend/app/schemas/agent_scan.py and tests/fixtures/agent_scan_v1.json", "content": {"application/json": {}}}}` keeps the entry. The contract lives in the schema module and the golden fixture, not in OpenAPI.
  - **This doesn't change who is authorized:** the same token check runs and the same callers succeed. What changes is the order. A request with no token and an invalid body now gets 401 where it used to get 422.
- **Content-Length handling.** A non-integer value is ignored, and the streaming cap still applies. h11 rejects malformed framing before the app sees it. Non-HTTP scopes (`lifespan`, `websocket`) pass through.
- **The pre-read file check** is `ensure_upload_size(file)`: a 413 if `file.size is not None and file.size > settings.MAX_UPLOAD_SIZE_BYTES`. It's called before `file.read()` in `save_upload`, `inventory._read_csv` and both vendor CSV routes. Starlette sets `UploadFile.size` while it spools the part, so the check reads no content into memory. `save_upload` keeps its post-read length check as the backstop for `size is None`. The CSV routes get the same 10 MiB cap as file uploads: the inventory CSV allows 10,000 rows of up to 4 × 255-character fields.
- **Residual:** multipart routes read and spool up to 10 MiB before authentication, because they're `UploadFile` params. That's bounded by the cap, and documented. It isn't changed here.

### T-PLAT-09: health
- **Both** `/health` and `/api/v1/health` check the DB. They share one handler, `app/api/routes/health.py::health_check`; `v1/health.py` registers the same function. Render uses `/health` (`render.yaml` L13).
- `SELECT 1` on `connect()`, inside `asyncio.wait_for(…, settings.HEALTH_DB_TIMEOUT_SECONDS)`, default **2.0** s. Any exception, or the timeout, means unreachable.
- **A dedicated engine:** `health_engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=1)` in `app/db/engine.py`.
  - If health used the app pool (`pool_size=10, max_overflow=20`, 30 s checkout), a saturated pool would turn into 503s, and Render would restart the instance mid-load.
  - The URL is the same one the app engine uses. Read it from `settings.DATABASE_URL`, after the validator at `config.py` L44 has normalised it.
- **Cached for 2 s, single-flight:** `HEALTH_CACHE_SECONDS: float = 2.0`. An `asyncio.Lock` guards a `(checked_at, ok)` pair. Concurrent callers inside the window share one query, so an unauthenticated flood of `/health` costs at most one `SELECT 1` every 2 s.
  - **`checked_at` is taken after the check completes,** and each caller re-reads the cache after it gets the lock. A slow check (up to 2 s against a blackholed DB) then serves all its queued waiters, rather than each running its own serial check.
  - Tests clear the cache with `health_service.reset_cache()`.
- **`pool_pre_ping=True` on `health_engine`,** so a connection the server killed (a DB restart) is replaced instead of producing one false 503. `close_db` disposes `health_engine` as well.
- **Body.** `HealthResponse` gains `database: str`, which is `"ok"` or `"unavailable"`. `status` is `"ok"`, or `"unavailable"` with HTTP 503. `service`, `version` and `environment` are unchanged, so no new information is exposed. There is never any error text.
- **Stays unauthenticated and rate-limit-exempt.** The routes have no `@limiter.limit` decorator and the limiter has no `default_limits` (`app/core/limiter.py` L7), so nothing changes. Render's checker must never be throttled.
- **Engine injection:** `app.db.engine.get_health_engine() -> AsyncEngine` returns `health_engine` and is the route's dependency. The 503 test overrides it with an engine on `127.0.0.1:9`, where nothing listens and the connection is refused at once, and disposes it afterwards.
- **Risk:** a DB outage now fails Render's health check. Render then holds a deploy or restarts the instance; it doesn't serve stale success. That's the intended T-PLAT-09 behaviour, recorded in the PR.

### T-UPL-09: agent HTTPS-only
- **Loopback only, no flag.** `http://` is accepted only when the host is `localhost` (case-insensitive) or an IP literal that `net.IP.IsLoopback()` accepts (127.0.0.0/8, `::1`). Anything else needs `https://`. A general `--insecure` flag would be a foot-gun, and loopback traffic never leaves the host.
- **The validation is in `upload.New`,** which now returns `(*Client, error)`, so no caller can skip it. `main.go` is the only caller.
- **No redirects.** The `http.Client` gets `CheckRedirect` returning `ErrRedirectRefused`. Go's default follows a 307/308 POST with its body, and it keeps `Authorization` on a same-host scheme downgrade. The API never redirects the agent's two exact paths, so refusing every redirect costs nothing.
- **Residual:** this protects agent builds from this commit on. The released `agent-v0.1.0` binaries don't enforce it, and the backend can't: by the time Render redirects an `http://` request, the token has already been sent. The threat-model row says so, and the next agent release (Arlo tags it) ships the fix.

### T-DOM-09: egress regression tests
- `_http_client()` is inspected directly: `client.follow_redirects is False`.
- **A behavioural test runs the real factory.** `dc.httpx.AsyncClient` is swapped for a subclass that injects a `MockTransport` and passes every other keyword through, `follow_redirects` and `verify` included. This isn't a mock of `_http_client`. If `follow_redirects` flipped to `True`, httpx would follow the redirect itself, and the transport would see a request to the redirect's hostname instead of the pinned public IP.
- **The port rule is tested through `check_http_headers`,** with a redirect to `https://www.example.com:8443/`. No request may reach `www.example.com`.

### Threat model
- **All five rows become TEST.** Each has a test that fails if its control is removed:
  - T-PLAT-01: a pytest test for the API and a unittest for `firebase.json`;
  - T-PLAT-06 and T-PLAT-09: pytest;
  - T-UPL-09: a Go test;
  - T-DOM-09: pytest.
  
  None is CONTROL-only. The SPA header values are proven by the unittest, and their effect in a browser by the owner check.
- **T-DOM-02 moves CONTROL → TEST.** Its Notes say it's CONTROL only because no test pins the real client or the port rule. Task 1 adds exactly those tests, so this stage-D precedent (T-TOK-06) applies.
- **The withdrawn T-UPL-06** keeps its `withdrawn:` Notes, with ` Closed with T-PLAT-06 in S4-E.` appended. The checker skips withdrawn rows.
- **The OPEN RISK S4 row is kept** as `none: all 14 rows closed in S4 (stages A–E); T-UPL-09 reaches operators only with the next agent release (owner step)`. The index then shows S4 as done rather than missing, without overclaiming for binaries already shipped. The checker doesn't parse the index.
- **Expected counts:** 110 = **39 CONTROL / 37 TEST / 18 ACCEPTED / 16 OPEN**. That's stage D's 40/31/18/21 with five OPEN → TEST and T-DOM-02 CONTROL → TEST. Count with the checker's parser (Task 7 Step 3), and use the real numbers if they differ.
- **`[K]` stays 20.** `[K]` counts routes whose authorization behaviour changed. Headers, the body cap and health are platform-wide. The agent upload's reorder runs the same check for the same callers. Only the order and the response to an unauthenticated invalid body change (401, where it was 422), and no caller gains or loses access. **`[N]` stays 128:** stage E adds no routes, and the route-count test pins it.

---

### Task 1: T-DOM-09 — egress regression tests

**Reviewer:** `reviewer-logic` (tests only).

**Files:**
- Modify: `backend/tests/test_domain_checks_egress.py` (add 3 tests after L282, `test_each_redirect_hop_uses_a_fresh_connection`)

**Interfaces:**
- Consumes: `dc._http_client` (`domain_checks.py` L124), `dc.check_http_headers`, and the `resolve` and `http` fixtures (L28, L42), plus `PUBLIC_V4`.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the tests.**
  - `test_real_http_client_does_not_follow_redirects`: `async with dc._http_client() as client: assert client.follow_redirects is False`.
  - `test_real_client_redirect_is_rechecked_not_followed(resolve, monkeypatch)`:
    - `resolve["ok.example.com"] = [PUBLIC_V4]`; `resolve["internal.example.com"] = ["10.0.0.7"]`;
    - the handler records requests and returns `302` with `location: http://internal.example.com/` for every request;
    - `real = httpx.AsyncClient`; `class _Recording(real)` with `__init__(self, **kw)` that sets `kw["transport"] = httpx.MockTransport(handler)` and calls `super().__init__(**kw)`; `monkeypatch.setattr(dc.httpx, "AsyncClient", _Recording)`. Don't touch `dc._http_client`;
    - `await dc.check_http_headers("ok.example.com")`;
    - assert `requests` isn't empty and `all(r.url.host == PUBLIC_V4 for r in requests)`.
  - `test_http_check_does_not_follow_a_redirect_to_a_non_default_port(resolve, http)`:
    - `resolve["ok.example.com"] = [PUBLIC_V4]`; `resolve["www.example.com"] = ["1.1.1.1"]`;
    - the handler returns `302` with `location: https://www.example.com:8443/` when `headers["host"] == "ok.example.com"`, and `200` otherwise;
    - assert no request has `headers["host"] == "www.example.com"`, and none has `url.port == 8443`.
- [ ] **Step 2: Run** `pytest tests/test_domain_checks_egress.py -v` (the gate command from Task 7 Step 5, with this target). Expected: all pass. The guards exist (T-DOM-02), so per-test red is owner-run (Task 7 Step 7).
- [ ] **Step 3: Commit** `test(egress): pin the domain-check client's redirect and port guards (T-DOM-09)`. Body: the real factory runs with only its transport replaced; the guards themselves are unchanged.

### Task 2: T-PLAT-09 — `/health` checks the database

**Reviewer:** `reviewer-risk` (production health signal).

**Files:**
- Create: `backend/app/services/health.py`
- Modify: `backend/app/db/engine.py` (add `health_engine`, `get_health_engine`), `backend/app/core/config.py` (add `HEALTH_DB_TIMEOUT_SECONDS`, `HEALTH_CACHE_SECONDS`)
- Modify: `backend/app/api/routes/health.py` (the shared handler), `backend/app/api/routes/v1/health.py` (register the shared handler; delete its duplicate model and function)
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  ```python
  # app/core/config.py
  HEALTH_DB_TIMEOUT_SECONDS: float = 2.0
  HEALTH_CACHE_SECONDS: float = 2.0

  # app/db/engine.py
  health_engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=1,
                                      pool_pre_ping=True)        # also disposed in close_db()
  def get_health_engine() -> AsyncEngine   # returns health_engine

  # app/services/health.py
  async def database_reachable(db_engine: AsyncEngine, *, timeout: float) -> bool
      # wait_for(connect + execute(text("SELECT 1")), timeout); any Exception or TimeoutError → False,
      # logged as warning "health: database unreachable (%s)" with type(exc).__name__ only
  async def cached_database_reachable(db_engine: AsyncEngine) -> bool
      # under an asyncio.Lock: re-read the cache; reuse it if younger than HEALTH_CACHE_SECONDS (time.monotonic),
      # else ok = await database_reachable(db_engine, timeout=HEALTH_DB_TIMEOUT_SECONDS); THEN checked_at = monotonic()
  def reset_cache() -> None                # tests only

  # app/api/routes/health.py
  class HealthResponse(BaseModel): status: str; service: str; version: str; environment: str; database: str
  async def health_check(response: Response, db_engine: AsyncEngine = Depends(get_health_engine)) -> HealthResponse
      # ok → 200 status "ok" database "ok"; unreachable → response.status_code = 503, status/database "unavailable"

  # app/api/routes/v1/health.py
  router.get("/health", response_model=HealthResponse)(health_check)   # same function, imported
  ```

- [ ] **Step 1: Write the failing tests** in `test_health.py`:
  - An autouse fixture calls `health_service.reset_cache()` before and after each test.
  - `_assert_health_body` additionally asserts `data["database"] == "ok"`. The four existing tests keep their names.
  - `test_health_503_when_database_unreachable` (parametrised over `"/health"` and `"/api/v1/health"`, `anon_client`):
    - `bad = create_async_engine("postgresql+asyncpg://health:health@127.0.0.1:9/none")`; `app.dependency_overrides[get_health_engine] = lambda: bad`;
    - GET → 503; `status == "unavailable"`, `database == "unavailable"`;
    - the response text contains none of `"127.0.0.1"`, `"health:health"`, `"Connect"`, `"Error"`;
    - in `finally`, pop the override and `await bad.dispose()`.
  - `test_database_reachable_times_out`:
    - a fake engine whose `connect()` returns an async context manager that awaits `asyncio.sleep(30)` on enter;
    - `await database_reachable(fake, timeout=0.05)` is `False`, and the elapsed time is under 1 s (`time.monotonic`).
  - `test_database_reachable_true_on_real_engine`: `await database_reachable(health_engine, timeout=2.0)` is `True`.
  - `test_concurrent_health_checks_share_one_query`:
    - a fake engine whose `connect()` counts calls and yields a connection whose `execute` returns after `asyncio.sleep(0.05)`;
    - `asyncio.gather(*(cached_database_reachable(fake) for _ in range(20)))` → all `True`, with `connect` called exactly once.
  - `test_health_cache_expires`: `monkeypatch.setattr(settings, "HEALTH_CACHE_SECONDS", 0.0)`; two sequential calls → `connect` called twice.
  - `test_slow_health_check_serves_queued_callers`: `HEALTH_CACHE_SECONDS` = 0.1. The fake's `execute` sleeps 0.3 s, which is longer than the cache window and shorter than the timeout. 20 concurrent `cached_database_reachable` calls → `connect` called exactly once (the timestamp is taken after the check).
- [ ] **Step 2: Run** `pytest tests/test_health.py -v`. Expected: an `ImportError` on `get_health_engine` or `database_reachable` (a collection-level red).
- [ ] **Step 3: Implement** per Interfaces. The docstring of `health_check` says: "Liveness plus a `SELECT 1`. 503 when the database is unreachable. Unauthenticated and not rate-limited (Render's health check)."
- [ ] **Step 4: Run** `pytest tests/test_health.py tests/authz -q`. Expected: all pass. The route table and dependency cross-check are unchanged: both routes are still `public` with no auth dependency.
- [ ] **Step 5: Commit** `feat(health): /health checks the database and returns 503 when it is unreachable (T-PLAT-09)`.

### Task 3: T-PLAT-06 — request-body limit, pre-read file check, agent auth before body

**Reviewer:** `reviewer-risk` (it changes when authentication runs on the agent route).

**Files:**
- Create: `backend/app/core/body_limit.py`
- Modify: `backend/app/core/config.py` (`MAX_JSON_BODY_BYTES`, `MAX_AGENT_UPLOAD_BYTES`, next to `MAX_UPLOAD_SIZE_BYTES` at L193)
- Modify: `backend/app/main.py::create_app` (add the middleware **first**, before `RequestContextMiddleware`, so it is innermost)
- Modify: `backend/app/services/file_upload.py` (`ensure_upload_size`; call it in `save_upload` before L69)
- Modify: `backend/app/api/routes/v1/inventory.py` (`_read_csv` L172; `read_agent_payload`; `upload_agent_scan` L443–447)
- Modify: `backend/app/api/routes/v1/vendors.py` (L332, L380: call `ensure_upload_size` before `file.read()`)
- Test: `backend/tests/test_body_limit.py`, `backend/tests/authz/tenancy/test_agent_body_limit.py`

**Interfaces:**
- Consumes: stage D's `_agents.py` (`issue_agent`, `scan_payload`, `UPLOAD`, `ACCEPTED`), `authz_client` and `snapshot_org`.
- Produces:
  ```python
  # app/core/config.py
  MAX_JSON_BODY_BYTES: int = 1024 * 1024            # 1 MiB
  MAX_AGENT_UPLOAD_BYTES: int = 80 * 1024 * 1024    # 80 MiB; arithmetic in the S4-E plan / PR body
  # superseded in review: AGENT_UPLOAD_BUDGET_BYTES = 32 MiB, AGENT_UPLOAD_ORG_BUDGET_BYTES = 24 MiB,
  # AGENT_UPLOAD_WAIT_SECONDS = 10.0 (replace AGENT_UPLOAD_CONCURRENCY and AGENT_LARGE_UPLOAD_BYTES)
  AGENT_UPLOAD_READ_TIMEOUT_SECONDS: float = 60.0

  # app/core/body_limit.py
  REQUEST_TOO_LARGE = "Request body too large"
  MULTIPART_OVERHEAD_BYTES = 64 * 1024
  def limit_for(path: str) -> int
      # f"{settings.API_PREFIX}/inventory/scans" → MAX_AGENT_UPLOAD_BYTES;
      # re ^{API_PREFIX}/organizations/[^/]+/(uploads|vendors/import(/preview)?|inventory/uploads/csv/(preview|import))$
      #   → MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES; else MAX_JSON_BODY_BYTES. Reads settings per call.
  class BodySizeLimitMiddleware:                    # pure ASGI
      def __init__(self, app: ASGIApp) -> None
      async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None
      # non-http scope → pass through. Declared content-length > limit → JSONResponse(413, {"detail": REQUEST_TOO_LARGE})
      # without calling receive. Else wrap receive: sum len(message["body"]) of http.request messages;
      # over limit → raise fastapi.HTTPException(413, REQUEST_TOO_LARGE).

  # app/services/file_upload.py
  def ensure_upload_size(file: UploadFile) -> None
      # 413 if file.size > cap; detail f"File exceeds maximum size of {cap_mb} MB", built from settings
      # exactly as save_upload builds it today (one shared helper for the text)

  # app/api/routes/v1/inventory.py
  AGENT_UPLOAD_BUSY = "Agent upload busy; retry shortly"
  AGENT_UPLOAD_TIMEOUT = "Agent upload timed out"
  class _AgentUploadGate:   # enrollments set, total bytes, bytes by org, waiter futures (one event loop, no locks)
      async def acquire(enrollment_id, org_id, size)   # duplicate enrollment -> 503 at once; else wait <= AGENT_UPLOAD_WAIT_SECONDS for budget and org share, then 503 + Retry-After: 5
      def release(enrollment_id, org_id, size)         # synchronous (safe in finally/cancel); wakes every waiter
  async def agent_upload_slot(request, enrollment=Depends(get_agent_from_token), session=Depends(get_session)) -> AsyncGenerator[int, None]
      # await session.commit(); weight = declared or MAX_AGENT_UPLOAD_BYTES when absent; await gate.acquire(...); try: yield declared; finally: gate.release(...)
  async def read_agent_payload(request: Request, declared: int | None = Depends(agent_upload_slot)) -> AgentScanPayload
      # async with asyncio.timeout(settings.AGENT_UPLOAD_READ_TIMEOUT_SECONDS): stream request.stream() into a local bytearray; > declared -> 413
      #   TimeoutError -> HTTPException(408, AGENT_UPLOAD_TIMEOUT); ClientDisconnect -> HTTPException(400, "Client disconnected")
      # ValidationError -> RequestValidationError (loc prefixed "body"); return AgentScanPayload.model_validate_json(buffer)
  # upload_agent_scan: payload: AgentScanPayload = Depends(read_agent_payload); openapi_extra per Decisions
  def _reset_agent_upload_slots() -> None            # tests only: replace the gate with a fresh one
  ```

- [ ] **Step 1: Write the failing tests** in `test_body_limit.py`. Use the `client` fixture (mock auth) for human routes, and `limiter.reset()` in an autouse fixture. Every 413 asserts the exact detail.
  - `test_limit_for_routes`:
    - `limit_for("/api/v1/inventory/scans") == settings.MAX_AGENT_UPLOAD_BYTES`;
    - each of the 5 file paths, with `{org_id}` = `1`, gives `settings.MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES`;
    - `"/api/v1/organizations/1/uploads/9"` and `"/api/v1/analytics/events"` give `settings.MAX_JSON_BODY_BYTES`.
  - `test_every_file_route_gets_the_file_limit`: for every `APIRoute` in `app.routes` whose `dependant.body_params` include an `UploadFile` field, `limit_for(path with every {…} replaced by "1")` equals the file limit. Any other route with a body (except the agent upload) gets `MAX_JSON_BODY_BYTES`. A new upload route without an entry fails here.
  - `test_declared_oversize_body_is_refused_unread` (pure ASGI, no HTTP client):
    - wrap a stub app that records whether it was called in `BodySizeLimitMiddleware`;
    - call it with an `http` scope for `/api/v1/analytics/events` with header `content-length: MAX_JSON_BODY_BYTES + 1`, a `receive` that records calls, and a `send` that collects messages;
    - assert `receive` was never called, the stub never ran, the start message status is 413, and the body JSON has the exact detail.
  - `test_json_body_over_default_limit_is_413`: POST `/api/v1/analytics/events` with `content=b" " * (MAX_JSON_BODY_BYTES + 1)` and `content-type: application/json` → 413.
  - `test_json_body_at_default_limit_is_not_413`: a valid analytics event JSON, right-padded with spaces to exactly `MAX_JSON_BODY_BYTES` bytes → its normal status, not 413.
  - `test_chunked_body_over_limit_is_413_and_read_stops[default-route|file-route]`:
    - `monkeypatch.setattr(settings, "MAX_JSON_BODY_BYTES", 256 * 1024)` and `monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 256 * 1024)`;
    - the content is an async generator of 64 KiB chunks, up to 4 MiB, counting the bytes it yields. httpx sends it chunked, with no `Content-Length`. Assert `"content-length" not in request.headers` with an event hook, or a check on the built request;
    - the targets are `/api/v1/analytics/events` (filler is spaces), and `/api/v1/organizations/{org}/uploads` with a `multipart/form-data; boundary=x` content type;
    - for the file route, the first chunk must be a valid part header, or python-multipart refuses the first byte with a 400 whatever the limit: `b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF'`, then filler bytes `b"a"`;
    - → 413, and the yielded bytes are at most `limit_for(path) + 64 * 1024` (the read stopped at the cap).
  - `test_file_route_allows_body_above_default_limit`: upload a 2 MiB PDF (starting with `%PDF`) to `/api/v1/organizations/{org}/uploads` → 201. Use `test_uploads.py`'s fixtures and `UPLOAD_DIR` handling.
  - `test_file_over_upload_cap_is_413_before_read[route]`, parametrised over the uploads route and the 4 CSV routes:
    - `monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)`;
    - spy on `starlette.datastructures.UploadFile.read` with a counter;
    - send a 4 KiB file (the request is under the 64 KiB overhead, so the middleware passes it). For the uploads route, use `application/pdf` with content starting `%PDF`: `save_upload` checks the type before the size. For CSV routes, use `text/csv`. → 413 with exactly the detail `ensure_upload_size` builds from the patched setting, and `read` was never called;
    - for the uploads route, no `org_uploads` row and no file under `UPLOAD_DIR`.
  - `test_maximal_agent_payload_fits_limit`:
    - build the maximal payload from the schema's own caps: read each field's `MaxLen` from `AgentScanPayload.model_fields[…].metadata` and `ScanSoftware`/`ScanService`/`ScanPort`/`ScanHost` `.model_fields`, so a raised cap changes the payload. Fill strings with `"a"`, use `port=65535`, `protocol="tcp"`, `schema_version="1.0"`, and a 64-character `scan_id`;
    - `body = json.dumps(p, separators=(",", ":")).encode()`;
    - assert `len(body) == 72_351_014` (the plan's arithmetic; a mismatch means the PR-body arithmetic is wrong), `AgentScanPayload.model_validate_json(body)` succeeds, and `len(body) <= settings.MAX_AGENT_UPLOAD_BYTES`.
- [ ] **Step 1b: Write the agent tests** in `tests/authz/tenancy/test_agent_body_limit.py` (module `world`, real verification). Each refusal also asserts that `snapshot_org(a)` is unchanged. Warm the token up with one status call first (gotchas, "S4 stage D").
  - `test_agent_upload_without_token_is_401_before_body_read`: an `authz_client` with no `Authorization` header. The content is an async generator of 1 MiB chunks, up to 8 MiB, counting yields. POST to `UPLOAD` → 401, and the yielded bytes are at most `1024 * 1024` (today FastAPI reads all 8 MiB first).
  - `test_agent_upload_over_limit_is_413`: `monkeypatch.setattr(settings, "MAX_AGENT_UPLOAD_BYTES", 64 * 1024)`; issue a token; the `scan_payload(a)` JSON, right-padded with spaces to `64 * 1024 + 1` bytes → 413.
  - `test_chunked_agent_upload_over_limit_is_413` (now `test_agent_upload_streaming_past_its_length_is_413`, with a declared Content-Length that the body outruns; a chunked upload is admitted as a maximal one and capped by the middleware):
    - the same limit and a valid token;
    - the body is an async generator: first the `scan_payload(a)` JSON minus its closing `}`, then 16 KiB chunks of spaces up to 1 MiB, with no `Content-Length`;
    - → exactly 413 (not 400 or 500; this is the case the pre-flight review showed fails if the middleware isn't innermost), the yielded bytes are at most `64 * 1024 + 16 * 1024`, and the snapshot is unchanged.
  - An **autouse fixture** in this module calls `_reset_agent_upload_slots()` before and after each test, so a held slot can't leak into later agent tests as spurious 503s.
  - **Holding the budget:** `await _agent_gate().acquire(fake_id, fake_org, size)`; release with `_agent_gate().release(...)` in `finally`.
  - `test_agent_upload_busy_is_503_unread_at_every_size`: fill the budget. With a valid token, send a small body with a Content-Length that counts yields → after the wait, 503 `AGENT_UPLOAD_BUSY`, `Retry-After: 5`, and 0 yielded bytes. Release the budget, then repeat the upload with a fresh payload → 201. Also: `test_chunked_upload_without_content_length_is_admitted_when_idle`, `test_body_without_content_length_is_weighted_as_a_maximal_upload`, `test_chunked_upload_over_the_maximum_is_413_and_releases_its_slot`, `test_second_upload_for_one_token_is_refused_at_once`, `test_many_small_uploads_from_different_enrollments_all_succeed`, `test_maximal_uploads_serialize_and_the_second_waits_for_the_first`, `test_org_share_stops_one_org_from_starving_another`, `test_waiting_for_room_holds_no_pool_connection`, `test_slow_small_upload_does_not_hold_a_pool_connection`, `test_cancelled_waiter_releases_its_reservation`.
  - (`test_small_agent_upload_skips_the_slot` was removed in review: small uploads are admitted by the byte budget like any other.)
  - `test_agent_upload_without_token_takes_no_slot`: fill the budget; a POST with no token → 401, not 503.
  - `test_stalled_agent_upload_times_out_and_frees_the_slot`:
    - `monkeypatch.setattr(settings, "AGENT_UPLOAD_READ_TIMEOUT_SECONDS", 0.2)`;
    - a valid token; a chunked generator that yields the first 1 KiB, then `await asyncio.sleep(5)`;
    - → 408 `AGENT_UPLOAD_TIMEOUT` within 2 s;
    - afterwards a chunked upload with a fresh payload → 201 (the slot was released).
  - `test_agent_upload_client_disconnect_is_400`, pure ASGI against `app`: an `http` scope for `UPLOAD`, with a valid token header and no `content-length`. `receive` returns `{"type": "http.disconnect"}`. Expect a 400 start message and no exception (`ClientDisconnect` doesn't reach `ServerErrorMiddleware`).
  - `test_agent_upload_at_limit_is_accepted`: the same limit; a fresh `scan_payload(a)` padded to exactly `64 * 1024` bytes → `ACCEPTED[UPLOAD]` (201).
  - `test_agent_upload_invalid_body_keeps_422_shape`: a valid token; body `{"schema_version": "1.0"}` → 422, and every `detail[i]["loc"][0] == "body"`.
- [ ] **Step 2: Run** `pytest tests/test_body_limit.py tests/authz/tenancy/test_agent_body_limit.py -v`. Expected: an `ImportError` on `app.core.body_limit` and on the slot names (a collection-level red). Without the reorder, the agent 401 test fails on the yielded-bytes assertion. That's the known T-PLAT-06 gap, not a stop.
- [ ] **Step 3: Implement** per Interfaces. Add the middleware in `create_app` **before** the `RequestContextMiddleware` line, so it ends up innermost (the order is in Decisions). In `upload_agent_scan`, keep `enrollment: AgentEnrollment = Depends(get_agent_from_token)`; FastAPI's per-request dependency cache makes it the same verification as the payload dependency's.
- [ ] **Step 4: Run** the Step 2 targets, then `pytest tests/test_agent_scan_routes.py tests/test_uploads.py tests/test_inventory_routes.py tests/test_org_vendors.py tests/authz -q`. Expected: all pass, including stage D's lifecycle and replay tests (the golden payload is about 1 KB). Update any failure per Task 8. Don't loosen it.
- [ ] **Step 5: Run** the full `pytest tests/ -q`. Expected: no 413 anywhere outside the new tests, so no legitimate body exceeds 1 MiB.
- [ ] **Step 6: Commit** `feat(platform): cap request bodies before they are read, and authenticate agent uploads before reading them (T-PLAT-06)`. Body: the three limits and the agent arithmetic at planning level; the pre-read file check; the auth-before-body reorder; the residuals (80 MiB on a 512 MB instance; multipart spooling before auth).

### Task 4: T-PLAT-01 — API security headers

**Reviewer:** `reviewer-risk`.

**Files:**
- Create: `backend/app/core/security_headers.py`
- Modify: `backend/app/main.py::create_app` (add the middleware last; register the `Exception` handler)
- Test: `backend/tests/test_security_headers.py`

**Interfaces:**
- Consumes: Task 3's `BodySizeLimitMiddleware` (for the 413 case).
- Produces:
  ```python
  # app/core/security_headers.py
  HSTS = "max-age=31536000; includeSubDomains"
  API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
  DOCS_CSP = "<the docs CSP in Decisions, verbatim>"
  def security_headers(path: str, docs_paths: frozenset[str]) -> dict[str, str]
      # the five headers; CSP = DOCS_CSP if path in docs_paths else API_CSP
  class SecurityHeadersMiddleware:                  # pure ASGI
      def __init__(self, app: ASGIApp, *, docs_paths: frozenset[str]) -> None
      # on http.response.start, append each header whose name isn't already present (case-insensitive)
  def internal_error_response(request: Request, docs_paths: frozenset[str]) -> PlainTextResponse
      # PlainTextResponse("Internal Server Error", 500) with security_headers(request.url.path, docs_paths)

  # app/main.py
  docs_paths = frozenset(p for p in (fastapi_app.docs_url, fastapi_app.redoc_url,
                                     fastapi_app.swagger_ui_oauth2_redirect_url) if p)
  ```

- [ ] **Step 1: Write the failing tests.** Use `anon_client`, or a `client` where auth is needed. `EXPECTED` is the dict from `security_headers("/x", frozenset())`, and `assert_headers(resp, csp=API_CSP)` checks every header's exact value.
  - `test_api_headers_on_representative_responses`, parametrised over these cases:
    - `GET /health` → 200;
    - `GET /api/v1/auth/me` with no token → 401;
    - `GET /no-such-path` → 404;
    - `POST /api/v1/analytics/events` with `{"event": 1}` (mock auth) → 422;
    - an oversize body (`MAX_JSON_BODY_BYTES` monkeypatched to 1024, a 2 KiB body) → 413;
    - `OPTIONS /api/v1/health` with `Origin: https://example.test` and `Access-Control-Request-Method: GET` → whatever CORS answers.
    
    Each case asserts the status, then `assert_headers`.
  - `test_headers_on_unhandled_500`:
    - `app.dependency_overrides[get_session]` = an async generator that raises `RuntimeError("boom-secret")`;
    - `AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), …)`;
    - `GET /api/v1/public/stats` → 500; `resp.text == "Internal Server Error"`; `"boom-secret" not in resp.text`; `assert_headers`;
    - pop the override in `finally`, and call `limiter.reset()`.
  - `test_docs_pages_get_the_docs_csp`: `GET /docs` and `GET /redoc` → 200, the CSP equals `DOCS_CSP`, and the other four headers equal `EXPECTED`.
  - `test_docs_csp_allows_the_assets_docs_pages_load`:
    - for `/docs` and `/redoc`, extract every `src="…"` and `href="…"` with an absolute `https://` URL from the HTML (a regex is enough);
    - each `<script src>` URL must match a `script-src` source, each stylesheet `<link href>` a `style-src` source, and each favicon an `img-src` source. The directives come from parsing `DOCS_CSP`. A source with a path (ending `/`) matches by origin plus path prefix; a source without one matches by origin;
    - an inline `<script>` without `src` requires `'unsafe-inline'` in `script-src`.
  - `test_existing_header_not_overwritten` (pure ASGI): a stub app that sends `x-frame-options: SAMEORIGIN` → it's kept, and the other headers are added.
- [ ] **Step 2: Run** `pytest tests/test_security_headers.py -v`. Expected: an `ImportError` (collection-level red).
- [ ] **Step 3: Implement** per Interfaces. In `create_app`: add `SecurityHeadersMiddleware` after the `CORSMiddleware` call (so it's outermost), and add `fastapi_app.add_exception_handler(Exception, lambda request, exc: internal_error_response(request, docs_paths))` (a named function is fine; ruff `ARG` applies).
- [ ] **Step 4: Run** `pytest tests/test_security_headers.py tests/test_body_limit.py tests/test_health.py tests/test_cors_guard.py tests/authz -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(platform): security headers on every API response, including errors, preflights and docs (T-PLAT-01)`.

### Task 5: T-PLAT-01 — Firebase Hosting headers for the SPA

**Reviewer:** `reviewer-risk`.

**Files:**
- Modify: `firebase.json` (add `hosting.headers`)
- Create: `.github/scripts/test_firebase_hosting_headers.py`

**Interfaces:**
- Produces:
  ```python
  # .github/scripts/test_firebase_hosting_headers.py
  ROOT = Path(__file__).resolve().parents[2]
  def spa_headers() -> dict[str, str]        # the "**" entry's headers from ROOT/firebase.json, names lower-cased
  def csp_directives(csp: str) -> dict[str, list[str]]
  class FirebaseHostingHeadersTests(unittest.TestCase): ...
  ```

- [ ] **Step 1: Write the failing tests** (`FirebaseHostingHeadersTests`):
  - `test_spa_sends_security_headers`: `x-content-type-options == "nosniff"`, `x-frame-options == "DENY"`, `referrer-policy == "strict-origin-when-cross-origin"`, and `content-security-policy` is present.
  - `test_spa_csp_blocks_framing_and_inline_script`:
    - `frame-ancestors == ["'none'"]`, `object-src == ["'none'"]`, `script-src == ["'self'"]`, `base-uri == ["'self'"]`;
    - no directive contains `'unsafe-eval'` or a bare `*`, and `script-src` has no `'unsafe-inline'`.
  - `test_spa_csp_allows_firebase_auth_endpoints` (Review Focus 1): `connect-src` contains `https://identitytoolkit.googleapis.com` and `https://securetoken.googleapis.com`.
  - `test_spa_csp_allows_the_production_api`: the origin of `VITE_API_BASE_URL` in `ROOT/frontend/.env.production` is in `connect-src`. **Limit:** CI builds with the `VITE_API_BASE_URL`, `VITE_FIREBASE_AUTH_DOMAIN` and `VITE_SENTRY_DSN` secrets (`ci.yml` L210–217, L255–262), which override the committed file. This test therefore pins only the committed value. Whether the secret origins match the CSP is an owner checkbox in the PR (Task 7 Step 8), and a CI check on them is a follow-up.
  - `test_spa_csp_allows_fonts_and_org_logo_images` (Review Focus 2): `https://fonts.googleapis.com` is in `style-src`, `https://fonts.gstatic.com` is in `font-src`, and `https:` is in `img-src`.
- [ ] **Step 2: Run** `python -m unittest discover -s .github/scripts -v` from the worktree root. Expected: the 5 new tests fail (there's no `headers` block); the existing 65 pass.
- [ ] **Step 3: Implement** the `headers` block per Decisions, with the CSP as one string in table order. Keep `public`, `ignore` and `rewrites` unchanged.
- [ ] **Step 4: Run** the unittest again (70 OK). Then, from `C:/dev/ht-s4-e/frontend`, each its own call: `npm run lint`, `npm test`, `npm run build`. Expected: 479 passed and the build OK (the frontend source is unchanged). Then grep `frontend/dist/index.html` for `<script>` without `src` and for a `style=` attribute; expect none. An inline script there would break `script-src 'self'`, so stop and report.
- [ ] **Step 5: Commit** `feat(frontend): security headers and a CSP for the SPA on Firebase Hosting (T-PLAT-01)`. Body: the origin table, condensed, and that the browser check is the owner's, on the preview channel.

### Task 6: T-UPL-09 — the agent refuses non-HTTPS servers and redirects

**Reviewer:** `reviewer-risk` (credential transport).

**Files:**
- Modify: `agent/internal/upload/client.go` (`ErrInsecureServer`, `ErrRedirectRefused`, `ValidateServerURL`, `New`)
- Modify: `agent/cmd/hacker-tracker/main.go` (`uploadScan` L146: handle `New`'s error; the `--server` flag help at L75)
- Create: `agent/internal/upload/client_test.go`
- Modify: `agent/README.md` (L102–114 flags table, L141 transport section), `docs/security/agent_enrollment.md` (L22)

**Interfaces:**
- Produces:
  ```go
  // agent/internal/upload/client.go
  var ErrInsecureServer = errors.New("--server must be an https:// URL; http:// is allowed only for localhost, 127.0.0.1 or [::1]")
  var ErrRedirectRefused = errors.New("server redirected the request; refusing to follow (use the final https:// URL as --server)")
  func ValidateServerURL(raw string) error   // url.Parse; Host non-empty; scheme https, or http with loopback Hostname(); else ErrInsecureServer (wrapped with the URL's scheme://host only, never the full string)
  func New(baseURL, token string, timeout time.Duration) (*Client, error)
      // ValidateServerURL first; HTTP: &http.Client{Timeout: timeout,
      //   CheckRedirect: func(*http.Request, []*http.Request) error { return ErrRedirectRefused }}
  ```
  The loopback test is `strings.EqualFold(h, "localhost")`, or `net.ParseIP(h)` non-nil and `IsLoopback()`.

- [ ] **Step 1: Write the failing tests** in `client_test.go` (package `upload`):
  - `TestNewRejectsPlainHTTPServer`: a table of `http://api.example.com`, `http://hacker-tracker-backend.onrender.com`, `http://localhost.example.com`, `http://127.0.0.1.nip.io`, `http://10.0.0.5:8000`, `ftp://api.example.com`, `api.example.com`, `https://` and `""`. Each gives `errors.Is(err, ErrInsecureServer)` and a nil client.
  - `TestNewAllowsHTTPSAndLoopbackHTTP`: `https://api.example.com`, `https://api.example.com/` (trailing slash, and `BaseURL` is trimmed), `http://localhost:8000`, `http://LOCALHOST:8000`, `http://127.0.0.1:8000`, `http://[::1]:8000`. Each gives a nil error.
  - `TestClientDoesNotFollowRedirects`:
    - `target := httptest.NewServer(...)` counts hits;
    - `origin := httptest.NewServer(...)` answers every request with `http.Redirect(w, r, target.URL+r.URL.Path, http.StatusTemporaryRedirect)`;
    - `c, err := New(origin.URL, "ht_abc_def", 5*time.Second)` (`origin.URL` is `http://127.0.0.1:…`, which is allowed);
    - `_, err = c.Upload(ctx, output.New("id", "nonce", output.Host{Hostname: "h"}, nil, nil, nil))`;
    - assert `errors.Is(err, ErrRedirectRefused)` and target hits `== 0`.
- [ ] **Step 2: Run** each in its own call, from the worktree:
  ```
  MSYS_NO_PATHCONV=1 docker run --rm -v C:/dev/ht-s4-e/agent:/src -w /src golang:1.27 go test ./...
  ```
  Expected: a compile failure. `ValidateServerURL` and the error vars are undefined, and `New` returns one value.
- [ ] **Step 3: Implement** per Interfaces. In `main.go`, `client, err := upload.New(server, apiKey, timeout)`; on error, return it unchanged, so the operator sees `ErrInsecureServer`'s text. The `--server` help reads: `backend base URL; must be https:// (http:// only for localhost), e.g. https://api.example.com (env HT_SERVER)`.
- [ ] **Step 4: Run**, each its own call:
  - `… golang:1.27 go vet ./...`;
  - `… golang:1.27 gofmt -l .` (expect no output);
  - `… golang:1.27 go test ./...` (expect `ok` for `internal/upload`, and the existing packages still `ok`).
- [ ] **Step 5: Docs.**
  - `agent/README.md`: the `--server` row says "must be `https://`; `http://` is accepted only for `localhost`, `127.0.0.1` or `[::1]`". The transport section gains "The scanner refuses a plain-HTTP server and never follows a redirect; builds before this change don't enforce this."
  - `agent_enrollment.md` L22: replace "neither the agent nor the backend enforces it" with "the agent refuses a non-HTTPS server (loopback excepted) and doesn't follow redirects; the API sends HSTS. Agent builds before the next release don't enforce this."
- [ ] **Step 6: Commit** `feat(agent): refuse a non-HTTPS server URL and never follow redirects (T-UPL-09)`.

### Task 7: Threat model, docs, S4 close-out, gate, PR

**Reviewer:** `reviewer-logic` (docs and counts).

**Files:**
- Modify: `docs/security/threat_model.md`:
  - T-UPL-06 (L129), T-UPL-09 (L132), T-DOM-02 (L210), T-DOM-09 (L217);
  - T-PLAT-01 (L267), T-PLAT-06 (L272), T-PLAT-09 (L275);
  - the T-AUTH-04 and T-TEN-07 Threat cells (tense);
  - the OPEN RISK S4 row (L307).
- Modify: `README.md`: L17–21 (direction), L162 (counts), L180 ("still in progress"), L194–197 (input boundaries); `docs/README.md` (check that it still says 110); `docs/PRODUCT_VIABILITY_ROADMAP.md` L263–283

- [ ] **Step 1: Rows.** Each one's Evidence is the listed test ids, in backtick `path::name` form.
  - **T-PLAT-01 → TEST.**
    - Evidence: `backend/tests/test_security_headers.py::test_api_headers_on_representative_responses`, `backend/tests/test_security_headers.py::test_headers_on_unhandled_500` and `.github/scripts/test_firebase_hosting_headers.py::FirebaseHostingHeadersTests::test_spa_csp_blocks_framing_and_inline_script`.
    - Notes: "API: HSTS, nosniff, DENY, no-referrer and a deny-all CSP on every response (docs pages get a narrower CSP); SPA: CSP, nosniff, DENY via `firebase.json`, HSTS from Firebase Hosting. Browser check on the preview channel is an owner step. Fixed in S4-E."
  - **T-PLAT-06 → TEST.**
    - Evidence: `backend/tests/test_body_limit.py::test_chunked_body_over_limit_is_413_and_read_stops`, `backend/tests/test_body_limit.py::test_file_over_upload_cap_is_413_before_read` and `backend/tests/authz/tenancy/test_agent_body_limit.py::test_agent_upload_without_token_is_401_before_body_read`.
    - Evidence also includes `backend/tests/authz/tenancy/test_agent_body_limit.py::test_chunked_agent_upload_over_limit_is_413`.
    - Notes: "Bodies are capped before they're read (1 MiB default, 10 MiB + overhead for file routes, 80 MiB for the agent upload, derived from the schema's list caps); the agent upload authenticates before reading its body and is admitted by a byte budget (see the revision above). Residuals (as first drafted, superseded by the T-PLAT-06 row in `threat_model.md`): the five multipart routes spool up to about 10 MiB per request before authentication. Absorbs T-UPL-06. Fixed in S4-E."
  - **T-PLAT-09 → TEST.**
    - Evidence: `backend/tests/test_health.py::test_health_503_when_database_unreachable`, `backend/tests/test_health.py::test_database_reachable_times_out`.
    - Notes: "`SELECT 1` with a 2 s timeout; 503 with no error text. Render's health check uses `/health`. Fixed in S4-E."
  - **T-UPL-09 → TEST.**
    - Evidence: `agent/internal/upload/client_test.go::TestNewRejectsPlainHTTPServer`, `agent/internal/upload/client_test.go::TestClientDoesNotFollowRedirects`.
    - Notes: "The agent refuses non-HTTPS servers (loopback excepted) and redirects; the API sends HSTS. Takes effect from the next agent release; `agent-v0.1.0` binaries don't enforce it, and the backend can't. Fixed in S4-E."
  - **T-DOM-09 → TEST.**
    - Evidence: `backend/tests/test_domain_checks_egress.py::test_real_http_client_does_not_follow_redirects`, `backend/tests/test_domain_checks_egress.py::test_real_client_redirect_is_rechecked_not_followed` and `backend/tests/test_domain_checks_egress.py::test_http_check_does_not_follow_a_redirect_to_a_non_default_port`.
    - Notes: "Closed in S4-E."
  - **T-DOM-02 → TEST.**
    - Evidence: five ids, each written out in full, because the checker's `EVIDENCE_RE` silently skips a token with no path before `::`:
      - `backend/tests/test_domain_checks_egress.py::test_http_check_does_not_follow_a_redirect_to_an_internal_host`;
      - `backend/tests/test_domain_checks_egress.py::test_http_check_does_not_follow_a_redirect_to_an_ip_literal`;
      - `backend/tests/test_domain_checks_egress.py::test_http_check_stops_after_the_redirect_limit`;
      - `backend/tests/test_domain_checks_egress.py::test_real_client_redirect_is_rechecked_not_followed`;
      - `backend/tests/test_domain_checks_egress.py::test_http_check_does_not_follow_a_redirect_to_a_non_default_port`.
    - Notes: drop the "CONTROL rather than TEST" sentences, and keep the description of the guard.
  - **T-UPL-06:** keep `withdrawn:` first in Notes, and append " Closed with T-PLAT-06 in S4-E."
  - **T-AUTH-04 and T-TEN-07 Threat cells:** rewrite in the past tense, "…did not require…", matching the fixed rows (todos, "S4 stage C"; stage-C deferred minor).
- [ ] **Step 2: OPEN RISK row.** S4 becomes `none: all 14 rows closed in S4 (stages A–E); T-UPL-09 reaches operators only with the next agent release (owner step)`.
- [ ] **Step 3: Recount.** Run this from the worktree root, in one call:
  ```
  python -c "import sys,collections; sys.path.insert(0,'.github/scripts'); import check_threat_model as c; rows,_=c.parse(open('docs/security/threat_model.md',encoding='utf-8').read()); live=[r for r in rows if not r.notes.startswith('withdrawn:')]; print(len(live), collections.Counter(r.cls for r in live))"
  ```
  Expected: `110` with CONTROL 39, TEST 37, ACCEPTED 18, OPEN 16. Use the real numbers everywhere if they differ.
- [ ] **Step 4: README and roadmap.**
  - `README.md`:
    - **L162:** the new counts; "16 open and scheduled for S5 or owner action".
    - **L17–21:** the threat model, the route-enumerating suite and the attested agent release with an SBOM are done (S1, S3, S4). The SAST/SCA gates are in place (S2) and become blocking once the owner applies T-CI-05. The next work is DAST and a manual AppSec pass (S5) and matcher accuracy against Trivy (S6).
    - **L180:** delete "the rest of roadmap milestone S4 is still in progress".
    - **L194–197:** "Request bodies are capped before they're read: 1 MiB by default, 10 MB per uploaded file (checked before the file is loaded into memory; multipart bodies are still spooled before authentication), and 24 MiB for the agent upload, derived from its per-list caps. The agent upload is authenticated before its body is read, must declare a Content-Length, and is admitted against a byte budget."
  - **Roadmap:**
    - the heading becomes `#### S4. Authorization assurance — DONE 2026-10-2X (PRs #226–#TBD)` (the controller fills the number after the PR exists);
    - add a `Delivered:` paragraph in the S3 style: 128 routes classified (with the per-class counts from L277), real verification, cross-tenant sweep over 76 org-scoped routes, `[K]` = 20 routes whose authorization changed, all 14 rows TEST, and stage E's platform work;
    - in the scope list (L267–275), mark each fixed row with its stage, e.g. `(done, S4-C)`;
    - append Stage E to Progress;
    - fill the résumé line: `[N]` = 128, `[K]` = 20.
- [ ] **Step 5: Gate**, each its own call.
  - Reuse `ht-s4-net`, `ht-s4-pg` and `ht-s4-venv`. Check them with `docker ps -a --filter name=ht-s4-pg`, and start the container if it's stopped.
  - Delete the leftover row: `docker exec ht-s4-pg psql -U postgres -d cyber_threat_test_db -c "DELETE FROM users WHERE email = 'testuser@example.com'"`. Don't drop or recreate the database.
  - Backend:
    ```
    MSYS_NO_PATHCONV=1 docker run --rm --network ht-s4-net -v C:/dev/ht-s4-e/backend:/app -v ht-s4-venv:/venv -v ht-pipcache:/root/.cache/pip -w /app -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@ht-s4-pg:5432/cyber_threat_test_db -e APP_ENV=testing python:3.11-slim sh -c "python -m venv /venv && /venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt && /venv/bin/ruff check app tests evals && /venv/bin/ruff format app tests evals --check && /venv/bin/alembic -c app/db/alembic.ini upgrade head && /venv/bin/alembic -c app/db/alembic.ini check && /venv/bin/pytest tests/ -q"
    ```
    Expected: ruff clean; `alembic check` clean (no migration in this stage); pytest 2112 + the new tests, 0 failed, 1 skipped. Record the runtime against about 105 s.
  - Frontend, in `C:/dev/ht-s4-e/frontend`: `npm run lint`, `npm test` (479), `npm run build`.
  - Agent: the three Go commands from Task 6 Step 4.
  - `python .github/scripts/check_threat_model.py docs/security/threat_model.md`: exit 0.
  - `python -m unittest discover -s .github/scripts`: OK (70).
- [ ] **Step 6: Commit** `docs(threat-model): close T-PLAT-01, T-PLAT-06, T-PLAT-09, T-UPL-09 and T-DOM-09; S4 done`.
- [ ] **Step 7: Owner-run mutation checks (hand to Arlo; don't run).** For each: make the edit, run the named test (with the gate command, or the Go/unittest command), confirm it fails, revert, and confirm `git -C C:/dev/ht-s4-e diff --stat` is empty.
  1. `domain_checks.py::_http_client`: `follow_redirects=False` → `True`. Then `test_real_http_client_does_not_follow_redirects` and `test_real_client_redirect_is_rechecked_not_followed` fail.
  2. `_fetch_public_hops`: drop `or url.port is not None`. Then `test_http_check_does_not_follow_a_redirect_to_a_non_default_port` fails.
  3. `main.py`: delete the `SecurityHeadersMiddleware` line. Then `test_api_headers_on_representative_responses` fails.
  4. `main.py`: delete the `Exception` handler. Then `test_headers_on_unhandled_500` fails.
  5. `body_limit.py`: delete the `Content-Length` check. Then `test_declared_oversize_body_is_refused_unread` fails.
  6. `body_limit.py`: delete the streaming count. Then `test_chunked_body_over_limit_is_413_and_read_stops` fails.
  7. `inventory.py`: make `payload: AgentScanPayload` a plain body param again. Then `test_agent_upload_without_token_is_401_before_body_read` fails.
  8. `inventory.py::_read_csv`: delete the `ensure_upload_size` call. Then `test_file_over_upload_cap_is_413_before_read[inventory-csv-preview]` fails.
  9. `services/health.py`: `return True` at the top of `database_reachable`. Then `test_health_503_when_database_unreachable` fails.
  10. `client.go::ValidateServerURL`: accept any `http://`. Then `TestNewRejectsPlainHTTPServer` fails.
  11. `client.go::New`: drop `CheckRedirect`. Then `TestClientDoesNotFollowRedirects` fails.
  12. `firebase.json`: delete `frame-ancestors 'none'`. Then `test_spa_csp_blocks_framing_and_inline_script` fails.
  13. `main.py`: move the `BodySizeLimitMiddleware` line to just before `CORSMiddleware`, so it's outside the `BaseHTTPMiddleware`s. Then `test_chunked_agent_upload_over_limit_is_413` errors with an `ExceptionGroup` (it would be a 500 in production), and `test_chunked_body_over_limit_is_413_and_read_stops` fails with a 400.
  14. `inventory.py::agent_upload_slot`: make it a no-op `yield 0`. Then `test_agent_upload_busy_is_503_unread_at_every_size` fails.
  15. `inventory.py::read_agent_payload`: remove the `asyncio.timeout`. Then `test_stalled_agent_upload_times_out_and_frees_the_slot` fails.
  16. `services/health.py::cached_database_reachable`: skip the cache. Then `test_concurrent_health_checks_share_one_query` fails.
- [ ] **Step 8: The controller pushes and opens the draft PR.**
  - Target `main`, title `S4-E: platform hardening (headers, body limit, DB health, agent HTTPS, egress tests)`. Verify `baseRefName == main`. Don't mark it ready.
  - Body (planning level, public repo):
    - start with `> Stacked on #229`;
    - the decisions above: header values and the docs CSP; the SPA origin table; the three body limits; **the agent arithmetic table** (per-item bytes, per-list totals, 72,351,014 total, 80 MiB limit, the non-ASCII caveat, the starter-plan residual); auth before body on the agent route; health behaviour; agent loopback-only HTTP and no redirects;
    - the threat-model counts, `[K]` = 20 and `[N]` = 128, with their reasoning;
    - a **"Decision for Arlo before merge"** section: lower the agent schema's per-list caps (say, 20,000 software, 5,000 services and 5,000 ports) and with them `MAX_AGENT_UPLOAD_BYTES`, or accept the 80 MiB residual, bounded by one upload at a time, until a later stage;
    - an unchecked **"Mutation check (owner)"** section with Step 7's 16 steps;
    - an unchecked **"Docs check (owner, before merge)"**: run the backend locally (docker compose or `uvicorn`), open `/docs` and `/redoc` with DevTools open, and expect no CSP violations. Use Swagger's "Try it out" on `/health`;
    - an unchecked **"CSP check (owner, before merge)"** section:
      1. Local: from `C:/dev/ht-s4-e/frontend`, run `npm run build` with your real `frontend/.env.production.local` values. Then, from the worktree root, run `npx --yes firebase-tools serve --only hosting --project hacker-tracker-75f91 --port 5050`. Open `http://localhost:5050` with DevTools open.
      2. Sign in, then visit the Dashboard (map and charts), Org profile (set a logo URL on another `https` host and check that the preview shows), Inventory, Settings (Members, Agents), Integrations and Privacy. Sign out and sign in again. Leave a tab open for more than an hour, or run `await auth.currentUser.getIdToken(true)` in the console, to exercise the token refresh.
      3. Repeat sign-in in **Safari (macOS or iOS)** as well as Chrome or Edge. Firebase's popup/redirect resolver may load the auth iframe and `apis.google.com` at startup on Safari and iOS.
      4. Expect **no** `Refused to …` / `Content-Security-Policy` console messages. Record whether the `firebaseapp.com` iframe loads, and which Sentry ingest host is called, if any.
      5. Repeat steps 2–4 on the PR's Firebase preview-channel URL (from the deploy-preview job). Then run `curl -sI <preview-url>` and confirm `content-security-policy`, `x-frame-options: DENY`, `x-content-type-options: nosniff` and `strict-transport-security` (from Firebase).
      6. **Secret origins (the unittest can't see them):** in the GitHub repo secrets, the origin of `VITE_API_BASE_URL` must be in `connect-src`, `VITE_FIREBASE_AUTH_DOMAIN` must equal the `frame-src` host (or `frame-src` is dropped per Decisions), and the `VITE_SENTRY_DSN` host must match one of the two ingest wildcards. Check these without pasting values anywhere.
      7. Any violation: paste it in the PR; the fix is a follow-up commit, not a weaker policy without review. If it's `apis.google.com` or the auth iframe, apply the `initializeAuth` fallback in Decisions.
    - an unchecked **"After deploy (owner)"** section:
      - Render's health check is green;
      - `curl -s https://hacker-tracker-backend.onrender.com/health` shows `"database":"ok"`;
      - `curl -sI` on the API shows the five headers;
      - `/docs` and `/redoc` render;
      - one real agent upload over `https://` still succeeds (201);
      - tag the next agent release so T-UPL-09 reaches operators (owner's call).
- [ ] **Step 9: Record follow-ups.** The controller writes these to Obsidian `todos.md` under "S4 stage E", with the stage-E gotchas and decisions:
  - **lower the agent schema's per-list caps** to realistic values (a coordinated schema change), then lower `MAX_AGENT_UPLOAD_BYTES`, unless Arlo takes this before merge. Today 80 MiB is a memory risk on the 512 MB starter plan for any self-registered account's agent;
  - a CI step that checks the build secrets' origins (`VITE_API_BASE_URL`, `VITE_FIREBASE_AUTH_DOMAIN`, the Sentry DSN host) against the `firebase.json` CSP without printing them;
  - the agent upload's rate limit still runs after the body is parsed; the slot is the bound. Consider checking the limit inside `read_agent_payload`;
  - a bounded retry in the Go agent that honours `Retry-After` on 503;
  - (resolved in review: the byte-budget gate with a per-org share replaced the single slot; what remains is that one org can make others wait up to 10 s, and the agent does not retry a 503 until the next agent release);
  - remove `frame-src` if the owner check shows the iframe never loads;
  - multipart routes still spool up to 10 MiB before authentication;
  - S5's ZAP baseline can now fail on missing headers (roadmap L293);
  - release the agent so T-UPL-09 reaches operators.

### Task 8: Existing tests the new rules change (reference list; each item is done in the task named)

Not a separate commit: Tasks 2–6 each update their own items. Surveyed 2026-10-23 at `16eb101`.

- **`tests/test_health.py`** (Task 2): the 4 tests keep their names; `_assert_health_body` gains `database == "ok"`. They hit the real test DB through the `client`/`anon_client` fixtures, so they pass unchanged otherwise.
- **`tests/test_agent_scan_routes.py`** (Task 3). It overrides `get_agent_from_token`, and the override also satisfies `read_agent_payload`'s sub-dependency, so it's expected unchanged.
  - `test_upload_unsupported_schema_version_422` (L195) still gets 422 from the handler's version gate.
  - A test that posts an invalid body without a usable token and expects 422 would now get 401. Update it to the new rule (auth before body), and say so in the commit body. None was found in the survey.
- **`tests/test_uploads.py`, `tests/test_inventory_routes.py`, `tests/test_org_vendors.py`** (Task 3): every file is far below 10 MiB, so they're expected unchanged.
- **`tests/test_cors_guard.py`** (Task 4): settings validation only; unchanged.
- **`tests/test_domain_checks_egress.py`** (Task 1): additions only.
- **`tests/authz/`** (Tasks 2–3):
  - the route table, the count (128) and the dependency cross-check are unchanged: health stays `public` with only `get_health_engine`, and the agent upload still depends on `get_agent_from_token` and not `get_current_user`;
  - stage A's "valid Firebase token on an agent route → 401" and stage B/D's agent-route cases still get 401 or 201;
  - a failure there means an ordering assumption broke. It goes to the controller and isn't fixed by loosening the case.
- **OpenAPI:** grep `tests/` for `openapi` and `requestBody`. A test that reads the agent upload's generated request schema is updated to the `openapi_extra` entry (Task 3). None was found in the survey.
- **`.github/scripts`** (Task 5): 65 → 70 tests.
- **Frontend Vitest** (Task 5): unchanged (479); the frontend source doesn't change.
- **Go** (Task 6): `internal/output` and `internal/collectors` tests are unchanged; `upload.New`'s new signature has one caller, `main.go`.
