# Ingest freshness runbook

How to tell whether production ingest data is fresh, and what to do when the daily check goes red. "The backend URL" is the production API base (the `BACKEND_URL` repo secret).

## Reading the endpoints

`GET /api/v1/ingest/health` (public) returns `healthy` and a `sources` map. Each source has:

- `stale`: server-computed against that source's threshold. Clients must not recompute it.
- `refresh_policy`: the effective policy, one of `scheduled`, `static` or `disabled`.
- `last_success_hours_ago`.
- `consecutive_failures`: failed attempts since the last completed run. A firing and its automatic retries count once (only chain heads, `retry_count == 0`), the same count catch-up uses for its backoff. Lock-contention `skipped` rows neither count nor reset it. A scheduled source with 2 or more makes `healthy` false, which means two bad firings.

IC3 is `static`: it is the 2021-2025 annual-report seed, so there is nothing newer to fetch. It is never refreshed by age and the daily check skips it.

A `scheduled` source whose cron is empty (`INGEST_SCHEDULE_*=""`) reports `disabled`: nothing will refresh it. The policy comes from the cron settings only, not from the serving instance's `SCHEDULER_ENABLED`, so every instance behind one URL reports the same policy (a secondary set to `false` does not turn sources `disabled`). If no instance runs the scheduler, scheduled sources stay `scheduled` and go stale once past their threshold, which turns the daily check red.

`static` and `disabled` sources are never stale by age, but one that has **never succeeded** counts as stale and makes `healthy` false (its failures alone do not). The daily workflow still skips them, so read `/api/v1/ingest/health` directly if a static source shows `stale: true`.

`GET /health` shows what is deployed and whether the scheduler is alive:

- `git_commit`: the deployed commit.
- `scheduler_enabled`: false means this instance runs no scheduled ingest. It is per instance: with several instances behind one URL, only the one running the scheduler shows true.
- `scheduled_jobs`: number of registered `ingest_<source>` jobs (sweeps, matcher and retention are not counted). With the defaults it is 4: NVD, KEV, EPSS and economics. A disabled source is not counted.

## Schedules and thresholds

| Source | Schedule (UTC) | Stale after |
|---|---|---|
| NVD | 01:00 daily | 25 h |
| CISA KEV | 01:15 daily | 25 h |
| EPSS | 02:00 daily | 49 h |
| Economics | 03:00 daily | 840 h |
| IC3 | none (static) | n/a |

Defaults live in `backend/app/core/config.py`. `INGEST_SCHEDULE_*` overrides a schedule; an empty value disables it (the source then reports `disabled`). Economics runs daily so a missed or failed run heals within 24 h, although Census ACS itself updates annually. The Census ingestor fails the run on any API error or incomplete response rather than loading demo data.

## Catch-up

On process start and from the hourly `catchup_sweep` job (`INGEST_CATCHUP_SCHEDULE`, default `:45` past each hour), both governed by `INGEST_CATCHUP_ON_STARTUP` (default on), every scheduled source that missed a cron firing since its last success is re-run, and any source with an empty table (including static IC3) is seeded. A static source is never re-run for age, even if given a cron. A source attempted recently is skipped: the guard is 1 hour, doubling per consecutive failed attempt up to 24 hours, so restart loops and failing upstreams are not hammered. Catch-up does not chain retries; the next catch-up is the retry.

## Triggering by hand

- UI: Pipeline Health tab.
- API: `POST /api/v1/ingest/trigger` (admin role required).
- Failed or stuck runs: `POST /api/v1/ingest/runs/{run_id}/retry` or `/cancel` (admin).

## Daily workflow

`.github/workflows/ingest-freshness.yml` runs at 06:00 UTC. It polls `/api/v1/ingest/health` on the backend URL for up to 30 minutes (so a cold instance and the startup catch-up can heal), skips `static` and `disabled` sources, and fails if any other source is not `stale == false`. It holds no source list or thresholds of its own.

## When it goes red

1. `/health` `git_commit` vs `main`: is the fix actually deployed?
2. Render deploy log: did `preDeployCommand` (migrations) fail and block the deploy?
3. Render dashboard: is a `SCHEDULER_ENABLED=false` override set? (`/health` shows `scheduler_enabled: false`.)
4. For the stale source, read `consecutive_failures` from `/api/v1/ingest/health` (or `/freshness`) and `error_message` from `/api/v1/ingest/runs` or the Pipeline Health tab. Fix the cause, then trigger it by hand.
5. If the workflow itself stopped running, GitHub disables schedules after 60 days of repo inactivity; re-enable it in the Actions tab.
