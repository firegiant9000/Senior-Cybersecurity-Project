# Ingest freshness: make production threat data refresh itself (design)

Date: 2026-10-25. Replaces PR #170 (`feature/adding-ic3-2025`, Ethan Gagliano, opened 2026-06-08).
Status: approved (Arlo, 2026-10-25). Section 8 owner answers still open; they gate PR 2, not PR 1.

## 1. Intent

Production threat data (NVD, CISA KEV, EPSS) has not refreshed since the first boot on about
2026-04-01. The product's claim is "live NVD CVE ingestion ... refreshed daily"
(`docs/PRODUCT_VIABILITY_ROADMAP.md` L278-280). Today that claim is false and nothing tells
anyone. This design makes the data refresh without a human watching, makes the freshness
badge honest, and makes "what is actually deployed" verifiable from CI.

The roadmap row for PR #170 (L38) says "DEFERRED, no assurance value". This work changes that
row: a dashboard that silently serves seven-month-old vulnerability data is an assurance
problem, and the fix is small.

## 2. What is actually wrong (evidence, 2026-10-25)

Facts gathered from the public endpoints and the repo; nothing here needed the Render dashboard.

1. **Nothing has ingested since first boot.** `GET /api/v1/ingest/health` shows nvd, cisa_kev
   and ic3 last succeeded 4,972 h ago (about 2026-04-01); economics and epss have *never*
   succeeded; `consecutive_failures` is 0 everywhere. `_auto_ingest()` in `backend/app/main.py`
   L63-97 seeds only *empty* tables, so the April 1 timestamp is the seed run. There has been no
   scheduled run, no failed run, no skipped run since.

2. **Production runs a stale build, and CI cannot see it.** `GET /openapi.json` is public in
   production. It contains the `/api/v1/agents/*` routes (merged 2026-06-13) but not the
   `finding_ids` field on the AI-summary schema (merged 2026-10-20, #202). So the live build is
   from the window 2026-06-13 .. 2026-10-19. Meanwhile `deploy-backend` in
   `.github/workflows/ci.yml` L305-317 reported success on every push to `main` through
   2026-10-26. The hook returns 200 whether or not Render's build or `preDeployCommand`
   (`alembic upgrade head`) later fails, and a failed Render deploy leaves the previous instance
   serving, so `post-deploy-healthcheck` (L336-345) passes on the old build. The missing
   security headers on `/health` (S4-E, #230 still open) are consistent with this.

3. **The scheduler is not firing in production.** EPSS has defaulted to `"0 2 * * *"` in
   `config.py` since 2026-05-22 (006b89b), which is older than the deployed build, so the job
   *should* be registered. It has never fired. The remaining explanations are all dashboard
   facts: `SCHEDULER_ENABLED=false` set in the Render environment, or the service is on Render's
   free plan and spins down after 15 idle minutes (the pilot has been "idle since June" per the
   Obsidian index), so the in-process APScheduler is not alive at 02:00 UTC. A cold-start
   latency probe is in progress to test the second theory.

4. **Consequence for #170.** Adding `INGEST_SCHEDULE_NVD/KEV` to `render.yaml` only helps if
   (a) the service is blueprint-synced so the env change applies, (b) a deploy actually lands,
   and (c) the process is awake at 03:00. None of those holds today. The frontend half of #170
   is sound in intent but dispatches its refresh event before the background run has done
   anything (`PipelineHealthTab.tsx`, the line right after `triggerIngestion`).

## 3. Goals, non-goals, anti-goals

Goals
- NVD, KEV and EPSS refresh at least daily in production with no manual step.
- If a scheduled window is missed (sleep, deploy, crash), the data catches up on the next
  process start instead of waiting up to 24 h.
- A stale source, a failed deploy, or a disabled scheduler becomes visible within a day,
  through a channel the owner already reads (GitHub Actions failure email).
- The freshness badge tells the truth: static data is labelled static, not "fresh" or "stale".
- CI fails when the commit it just "deployed" is not the one production is serving.

Non-goals
- Real IC3 PDF ingestion (roadmap Month 5, DEFERRED). `ic3_real.py` with `use_pdf=False`
  loads hardcoded annual figures and will keep doing so.
- Moving the scheduler to a Render Cron Job or a worker service. Costs money; the in-process
  scheduler plus catch-up-on-start is enough for one instance.
- KEV diff alerts (roadmap L38).

Anti-goals (would make this a failure even if it "works")
- Making static IC3 look fresh by scheduling a no-op monthly run (what #170 did).
- Duplicate concurrent ingestion. The advisory lock in `_run_ingestion` already prevents it;
  nothing here may bypass `_run_ingestion`.
- Any secret, key, DSN or connection string in the PR, logs, `/health`, or this document.
- Hitting NVD harder than today. One daily run plus at most one catch-up per process start.

## 4. Constraints

- Single uvicorn worker (`backend/Dockerfile` CMD), single Render instance, Postgres on Render.
- Nightly window order must stay: NVD, then EPSS 02:00 (scores for the freshest CVE set), then
  matcher sweep 02:30, CPE backfill 04:00, retention 05:00 (`config.py` L123-138).
- Gate: backend `ruff check`, `ruff format --check`, `pytest`; frontend `npm run lint`,
  `npx tsc --noEmit`, `npm test`, `npm run build` (see `ci.yml`). Backend tests need
  `alembic upgrade head` first (gotchas, S2 stage D).
- Public repo. Credit #170 and Ethan in the PR body. No "Generated with Claude" lines.
- Owner-only steps (Render dashboard, closing a teammate's PR) are written down for Arlo, not
  done by the implementer.

## 5. Design

Two PRs off `main`, in this order. PR 1 is the fix; PR 2 is the honesty and UX work. Each is
reviewable alone and PR 1 can deploy before PR 2 is written.

### PR 1: `fix/ingest-self-healing` (the data refreshes, and we can prove what is deployed)

**1a. Schedules become code defaults, not blueprint env.**
In `config.py`: `INGEST_SCHEDULE_NVD = "0 1 * * *"`, `INGEST_SCHEDULE_KEV = "15 1 * * *"`.
EPSS already works this way; the EPSS case proved that relying on `render.yaml` env sync is
exactly the path that failed. `render.yaml` gets a comment pointing at the code defaults and
documenting `SCHEDULER_ENABLED=false` as the local-dev opt-out. The existing scheduler tests
(`tests/test_scheduler.py`) gain a test that the production defaults register `ingest_nvd`,
`ingest_cisa_kev` and `ingest_epss` with the intended fire order (NVD before EPSS).

**1b. Catch-up on startup.**
`_auto_ingest()` in `main.py` generalises from "seed if empty" to "seed if empty **or** stale
beyond its threshold, for every source that has a schedule". It reads `ingest_runs` the same
way `get_ingest_health` does (last `completed` run per source vs `INGEST_STALE_HOURS_*`), then
runs the stale ones sequentially in the background in the existing order (NVD, KEV, then
EPSS), through `_run_ingestion(source, trigger="startup")` so locks, retries and run records
all apply. Sources with no schedule and no rows keep today's seed behaviour. New setting
`INGEST_CATCHUP_ON_STARTUP: bool = True`. A `trigger` value of `"startup"` is new; the
`PipelineHealthTab` trigger column already renders free text.

Why this is the load-bearing change: it makes freshness independent of whether the process
was alive at 01:00. A free-plan instance that sleeps will catch up the moment anything wakes
it (see 1d). A deploy that restarts the process at 00:59 no longer costs a day.

Thresholds today (`config.py` L153-157): NVD 25 h, KEV 25 h, IC3 168 h, ECON 168 h,
EPSS 49 h. Economics is **out of PR 1**: it gets a schedule, a policy and a threshold in PR 2
once section 8.3 is answered. Until then it stays unscheduled, and catch-up skips it because
it has no schedule (the existing seed path only covers nvd, cisa_kev and ic3, and that stays).

Move the catch-up logic into `backend/app/services/ingest_catchup.py` so it is unit-testable
without the FastAPI lifespan: given a list of `(source, last_success_at)` and the thresholds,
return the ordered list to run. Tests: never-run scheduled source is selected; fresh source is
not; stale source is; unscheduled source with rows is not; unscheduled empty source is (seed
path preserved); order is NVD, KEV, EPSS regardless of input order.

**1c. `/health` reports the deployed commit, and CI asserts it.**
`backend/app/api/routes/health.py` adds `git_commit` (first 12 chars of `RENDER_GIT_COMMIT`,
which Render injects into every service; fallback `GIT_COMMIT` build-arg for local Docker;
`"unknown"` otherwise), `scheduler_enabled` and `scheduled_jobs` (count of registered jobs,
read from the APScheduler instance; 0 when disabled). No hostnames, no env dump.
`post-deploy-healthcheck` in `ci.yml` polls `/health` for up to 10 minutes until
`git_commit` equals the first 12 chars of `github.sha`, and fails otherwise with a message
that says which commit is live (or `unknown`, which means the env var is missing and is its
own finding). This turns "Render deploys silently fail" from invisible to a red run on the
next push. It also lets anyone verify the live commit without dashboard access. Keep the
existing 200 check as the first step so a totally-down service still reads clearly.

The step is blocking, not `continue-on-error`. It runs only on push to `main`, after the
merge, so a red run never blocks a PR; it only emails the owner, which is the point. If
Render deploys are broken for an unrelated reason (section 1f), every push stays red until
that is fixed, and that is the correct signal. `RENDER_GIT_COMMIT` is injected for
Git-linked builds, which this service is (`runtime: docker` with `dockerfilePath` in
`render.yaml`); the `GIT_COMMIT` build-arg fallback is for local Docker only.

**1d. Daily external freshness check (zero cost).**
New workflow `.github/workflows/ingest-freshness.yml`: `schedule: "0 6 * * *"` plus manual
dispatch. It fetches `${BACKEND_URL}/api/v1/ingest/health` (public, no auth; `BACKEND_URL`
is the existing bare-origin secret that `ci.yml` L339 already appends `/health` to), prints
the per-source table, and fails if any source in a **hardcoded list** `nvd cisa_kev epss` has
`last_success_hours_ago` null or above a hardcoded threshold (25, 25, 49 h, mirroring
`INGEST_STALE_HOURS_*`). In PR 1 the workflow ignores the `healthy` flag on purpose: until
PR 2 lands, `healthy` is false because IC3 and economics count as stale, and a check that is
red from day one teaches people to ignore it. PR 2 switches the workflow to the
`refresh_policy` field and drops the hardcoded list.

Timing: a 01:00 run against a 25 h threshold leaves a 06:00 check well inside the window. If
the first fetch is slow or 5xx the workflow keeps polling every 2 minutes for up to 30
minutes before judging: on a free-plan instance the first request wakes the process, startup
catch-up (1b) runs NVD then KEV then EPSS, and a later poll sees fresh data. NVD's run length
is not measured anywhere in the repo (20,000-result cap, keyed API), so 30 minutes is a guess
the builder should confirm from the first `ingest_runs` durations after deploy and tighten.
A failing run emails the owner, which is the alert channel this project already has.

**1e. Misfire grace.**
Raise `misfire_grace_time` on the five ingest jobs from 300 s to 3600 s. Cheap, and it covers
an event loop that was busy (large upload, long matcher sweep) across the top of the hour.
Leave the matcher, backfill and retention jobs as they are.

**1f. Owner steps written into the PR body (Arlo does them; the implementer writes them).**
If the Render deploy log shows failures at `preDeployCommand` (Alembic), that becomes a
**PR 0** ahead of this one; PR 1 is still written and merged in the meantime, and its 1c check
stays red until PR 0 deploys, which is accurate.
- Render dashboard: confirm the service plan (free vs starter), whether auto-deploy is on, and
  open the most recent deploy's log. If deploys fail at `preDeployCommand`, the fix is a
  migration problem and comes first (gotchas: 021 duplicated, 024 and 041 missing).
- Confirm no `SCHEDULER_ENABLED` override exists in the dashboard env; delete it if it says
  `false`.
- After PR 1 deploys: the new `/health` shows `git_commit` matching `main`, and within an hour
  `/api/v1/ingest/health` shows nvd, cisa_kev and epss not stale (startup catch-up).

### PR 2: `feat/ingest-freshness-honest-badge` (the badge tells the truth)

**2a. Per-source refresh policy on the server.**
A small registry in `backend/app/services/ingest_sources.py`:
`{"nvd": "scheduled", "cisa_kev": "scheduled", "epss": "scheduled", "economics": <per 8.3>,
"ic3": "static"}`. `get_ingest_health` and `get_ingest_freshness` add `refresh_policy` and a
server-computed `stale: bool` to each source item. A `static` source is never stale and does
not affect `healthy`. `INGEST_STALE_HOURS_IC3` is kept only so a future real IC3 ingest can
flip the policy back to `scheduled` without a config migration.

**2b. Frontend uses the server's judgement.**
`frontend/src/api/ingest.ts` adds `stale` and `refresh_policy` to `SourceFreshness`.
`DataFreshness.tsx` drops its hardcoded 24 h `STALE_THRESHOLD_MS` and uses `s.stale`. A
`static` source renders as `IC3: static (2021–2025 annual reports)` with its own class and no
stale/error glyph. Keep #170's 5-minute poll and the `freshness:refresh` window event, but
pause the poll while `document.hidden` (mirror `PipelineHealthTab` L144-164).

**2c. Dispatch the refresh event when it can show something new.**
In `PipelineHealthTab.tsx`: dispatch `freshness:refresh` inside the existing 2 s
`refreshTimerRef` callback after a manual trigger, and again in the running-to-idle transition
at L138 (where `fetchData` already fires). Remove the immediate post-trigger dispatch #170 had.

**2d. Tests.**
Backend: freshness and health include `refresh_policy` and `stale`; a static source with a
7-month-old run reports `stale: false` and does not flip `healthy`. Frontend: new
`DataFreshness.test.tsx` under the existing Vitest setup: initial fetch; interval re-fetch
with fake timers; re-fetch on `freshness:refresh`; static label rendering; no poll while
hidden. `PipelineHealthTab` gets one test that the event fires after the 2 s timer and not
synchronously.

**2e. Docs.**
`docs/runbooks/ingest-freshness.md` (new, short): how to read `/api/v1/ingest/health` and
`/health`, how to trigger a source by hand, what the daily workflow checks, what to look at in
Render when it goes red. Update roadmap L38 to point here and drop "DEFERRED". Update
`render.yaml` comments. Frontend privacy page is unaffected (no new data categories).

### Close-out (owner-gated)
Comment on #170 thanking Ethan, linking both PRs, and close it. Only after Arlo says yes.
Delete the local `merge/ic3-2025-with-main` branch (never pushed).

## 6. Decided (my calls, open to override)

- Schedules live in code defaults (1a). Blueprint env stays as an override channel only.
- NVD `0 1 * * *`, KEV `15 1 * * *`. KEV is a 1 MB JSON fetch; 15 minutes after NVD is plenty.
- Catch-up runs sequentially, never concurrently, and never for `static` sources.
- `/health` exposes a 12-char commit, not the full SHA or branch name. No instance id.
- The daily workflow treats a `static` source as never stale, so IC3 cannot page anyone.
- Two PRs, not one. PR 1 fixes production; PR 2 can wait for a review cycle.
- Trigger label `"startup"` rather than overloading `"scheduled"`, so the runs table shows
  why a 00:xx run happened after a deploy.
- The CI commit assertion (1c) is blocking from day one. Post-merge only, so it emails rather
  than blocks.
- The daily workflow (1d) hardcodes nvd/cisa_kev/epss and their thresholds in PR 1 and
  ignores `healthy` until PR 2 adds `refresh_policy`.
- Economics is PR 2 scope only (needs 8.3).
- Deploy-failure root cause, if it is migrations, is a separate PR 0 and not folded in here.

## 7. Left to the builder

- Exact shape of the health/freshness pydantic additions, as long as the names above hold.
- Whether `ingest_catchup.py` takes an `AsyncSession` or a pre-fetched list (prefer the list;
  it is the testable seam).
- How the workflow retries (bash loop vs an action); keep it dependency-free and SHA-pinned per
  the S2 rules.
- Test file placement, following the existing `backend/tests/test_ingest_*.py` and
  `frontend/src/**/__tests__/` conventions.

## 8. Waiting on Arlo

1. **Render facts** (needed before PR 1 can be declared fixed, not before it is written): plan
   tier, auto-deploy state, last successful deploy's commit, any dashboard `SCHEDULER_ENABLED`
   or `INGEST_SCHEDULE_*` overrides, and whether the service is blueprint-synced.
2. **IC3 staleness:** recommend `static` (never stale, labelled). Alternative: keep it
   scheduled-but-static with a 1-year threshold. The design assumes `static`.
3. **Economics:** it has never run. `econ.py` uses `CENSUS_API_KEY` (set per
   `docs/month1_2_operational_closeout.md`) and works unauthenticated with a warning. Census
   ACS updates annually. Recommend `scheduled`, `"0 3 1 * *"` (monthly), threshold
   `INGEST_STALE_HOURS_ECON = 840` (35 days), and let startup catch-up do the first run.
   Alternative: leave it `manual` and out of `healthy`.
4. **Permission to comment on and close #170** once PR 1 is merged.
