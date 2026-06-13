# Month 3 Execution Plan — Version-Aware CVE Matching + Risk Scoring

> **Status: code-complete; all six phases + prior gaps closed (2026-06-13).** This document decomposes Month 3 of [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md) into numbered, independently-shippable phases. All six phases are implemented and tests pass locally; the two functional gaps flagged earlier (CPE backfill of the existing corpus, M365→asset persistence) plus the QA gaps (manual smoke doc, Vitest) are now **closed** — see "What's left to implement". Only process/hygiene items remain (go/no-go interview evidence, commit/PR). Work is uncommitted on branch `feature/month3-cpe-matching-plan`. Supersedes the roadmap's Month 3 task tables where they are now stale.
>
> **Headline finding:** ~60% of the roadmap's stated Month 3 scope already shipped in Months 1–2 (EPSS, the `cpe_match_cache` and `vendor_aliases` tables, the findings engine, an org-level risk scorer, and the assets/findings UI). The genuinely greenfield work is the **version-aware CPE→CVE matcher** and its **regression harness**. The roadmap was written before that pull-forward; do not rebuild what exists.

---

## Current state (what already exists — reuse, do not rebuild)

| Roadmap item (Month 3) | Actual status | Evidence |
|---|---|---|
| **WS 3.0 — EPSS ingestion** | ✅ **Fully done in Month 2.** Ingestor, daily scheduler job, columns, API exposure, `/ingest/health` staleness, `data_status` registry, tests. | `backend/app/ingestors/epss.py`; scheduler `INGEST_SCHEDULE_EPSS`; migrations 025 + 038 (`epss_score`/`epss_percentile`/`epss_fetched_at` on `cves`); `test_epss_ingest.py` |
| `cpe_match_cache` table | ✅ Table exists, **empty** — scaffolding awaiting the matcher | `backend/app/db/cpe_match_cache.py`, migration 037 |
| `vendor_aliases` table | ✅ Exists, seeded ~50 aliases | `backend/app/db/vendor_alias.py`, repo `vendor_aliases.py`, migration 037 |
| `asset_software.cpe_uri` | ✅ Column exists, nullable, **unpopulated** | `backend/app/db/asset_software.py` |
| Findings surface | ✅ Findings engine + `finding_statuses` table + UI exist | `findings_engine.py`, migrations 028/029, `FindingsTab.tsx`, `RiskScoringTable.tsx`, `AssetsPage.tsx` |
| Org-level risk scorer | ✅ Exists (SMB org score) — **NOT** per-finding | `backend/app/services/risk_scoring.py`, `smb_risk_score.py` |
| Assets / findings UI | ✅ Asset list + drill-down + EPSS column | `AssetsPage.tsx`, `NvdTable.tsx` |
| CI (pytest/ruff/alembic check) | ✅ Runs on every PR; **no nightly job** | `.github/workflows/ci.yml` |

### What is genuinely MISSING (the real Month 3)

> **Historical snapshot (2026-06-12).** This was the gap list at planning time. As of 2026-06-13 items 1–7 are **implemented** (see the per-phase ✅ notes); item 8 (M365→matcher) remains partial. The two genuinely-open items are now consolidated under **"What's left to implement"** below.

1. **Version-aware CPE→CVE matching logic.** No `cpe_matcher.py`. Current matching everywhere is **literal vendor+product string matching, version-blind**:
   - `services/inventory_import.py::count_kev_matches` — case-insensitive vendor+product against KEV only.
   - `services/vendor_matching.py` / `findings_engine.py` — name-only KEV vendor normalization.
2. **CPE criteria are discarded.** `repositories/exploited_vuln.py::_extract_vendor_product` parses only vendor (idx 3) + product (idx 4) from the CPE URI; `versionStartIncluding`/`versionEndExcluding`/etc. are dropped. NVD CPE configurations are not stored anywhere.
3. **No rate-limit-aware NVD CPE fetcher** to populate `cpe_match_cache` (the NVD fetcher we have is for CVEs, in `ingestors/nvd.py`).
4. **No persistent `asset_findings` table.** Findings are recomputed in-memory per request in `inventory.py` (`GET /assets/{id}/findings`); there is nowhere to store `match_confidence`, per-finding `risk_score`, `status`, or `false_positive_reported_by`.
5. **No per-finding risk scorer** (the existing one is org-level).
6. **No matcher regression suite** and **no nightly CI job**.
7. **No "report false positive" UI** and no confidence-tier display on findings.
8. **M365 device output not wired to the matcher** (carryover #124).

### Existing branch / PR findings (per investigation rule 6)

- `feature/risk-scoring-tables`, `feature/findings-engine-and-ai-summary` — **already merged** into main.
- `Risk-Scoring-and-fix-dashboard` — **unmerged but superseded.** Main has a richer `risk_scoring.py` + `smb_risk_score.py`; the branch's `smb_risk.py` schema no longer exists in main. **Do not resurrect.**
- Open PRs: only **#170** (ingest cron/freshness badges) — unrelated. No open PR touches CPE matching, version-aware matching, or a matcher regression suite.
- Carryover from Month 2 handoff: CycloneDX SBOM import (#115), Google Workspace OAuth, wire M365 → matcher (#124).

---

## Phased plan

Dependency order: **Phase 1 → 2 → 3** are the critical path. Phase 4 depends on 2+3. Phases 5 and 6 can start as soon as Phase 2/3 land and run in parallel. Phase 0 is a gate that runs first.

### Phase 0 — Confirm baseline & open issues (½ day, gate) — ✅ baseline verified 2026-06-12
- ✅ Verified EPSS, `cpe_match_cache`, `vendor_aliases`, `asset_software.cpe_uri` present on main: `backend/app/ingestors/epss.py`; `backend/app/db/cpe_match_cache.py`; `backend/app/db/vendor_alias.py`; `asset_software.cpe_uri` (`backend/app/db/asset_software.py:31`, `String(500)`, nullable).
- ✅ Confirmed migration head is **044** (`044_add_asset_tags_and_scan_provenance.py`, `revision="044"`, `down_revision="043"`; nothing references `down_revision="044"`). New migrations start at **045**.
- ✅ Relabeled the stale roadmap Month 3 WS 3.0 (EPSS) tasks as done in [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md) Workstream 3.0.
- ⏳ Open issues per phase below; do **not** reopen `Risk-Scoring-and-fix-dashboard`. (Pending team confirmation — not auto-created.)
- **Exit:** team agrees the matcher + regression harness is the actual scope.

### Phase 1 — Preserve CPE criteria + rate-limit-aware NVD CPE fetcher (data layer) — ✅ implemented 2026-06-13
*Owner suggestion: backend/data. Blocks everything.*

> Delivered: migration `045` (`cve_cpe_match` table, `down_revision="044"`, indexes on `cve_id` and `(vendor, product)`), model `backend/app/db/cve_cpe_match.py`, and `backend/app/ingestors/nvd_cpe.py` whose `parse_cpe_configurations()` now preserves all four version-bound segments (handles both API-2.0 list-form `configurations` and nested child nodes). `repositories/exploited_vuln.py::_extract_vendor_product` was rewritten to delegate to that parser instead of dropping version data. CPE criteria persist inline during NVD CVE ingest, gated by `NVD_CPE_PERSIST_ON_INGEST` (default true); `NVD_CPE_CACHE_TTL_HOURS` (168) and `NVD_CPE_BATCH_SIZE` (50) added to `core/config.py`. Parser unit tests in `tests/test_nvd_cpe_parser.py` (5 cases, real Log4Shell payload) — passing.
>
> **✅ Backfill wired (2026-06-13).** Closed the original gap: `backend/app/workers/cpe_backfill_job.py::run_cpe_backfill_sweep` runs a bounded, advisory-lock-guarded backfill of the pre-existing CVE corpus. Registered as a nightly scheduler job behind `NVD_CPE_BACKFILL_SCHEDULE` (default `0 4 * * *`, after the NVD window) and exposed for the initial one-shot via `POST /api/v1/ingest/cpe-backfill` (admin). `NVD_CPE_BACKFILL_MAX_PER_RUN` (default 500) caps NVD load per run; the TTL skip makes successive runs converge then no-op. Tests in `tests/test_cpe_backfill_job.py` (lock-held skip, limit pass-through, release-on-error).

1. **Migration 045** — new `cve_cpe_match` table storing per-CVE CPE criteria: `cve_id`, `cpe_uri`, `vendor`, `product`, `version_start_including`, `version_start_excluding`, `version_end_including`, `version_end_excluding`, `vulnerable` (bool). (The existing `cpe_match_cache` is a *normalized-name → CPE* lookup; this new table is the *CVE → affected-version-ranges* source of truth. Keep them separate.)
2. Stop discarding version segments in `repositories/exploited_vuln.py::_extract_vendor_product`; capture full criteria into `cve_cpe_match` during NVD ingest.
3. Extend `ingestors/nvd.py` (or a new `ingestors/nvd_cpe.py`) to persist CPE configurations. Reuse the existing rate-limit handling (1.2s/2.0s delay, 429 backoff, key fallback — `nvd.py:199,144-162`).
4. Add `NVD_CPE_*` settings to `core/config.py` following the existing pydantic pattern (TTL, batch size).
- **Verification:** ingest a known CVE (e.g. a Log4j/OpenSSL CVE) and assert the version ranges land in `cve_cpe_match`. Unit test the criteria parser.
- **Risk:** NVD rate limits throttle backfill → mitigate with caching + nightly incremental, not a full re-pull.

### Phase 2 — CPE matcher service with confidence levels (service layer, critical path) — ✅ implemented 2026-06-12
*Owner suggestion: lead dev. Hardest piece.*

> Delivered in `backend/app/services/cpe_matcher.py` (+ `backend/tests/test_cpe_matcher.py`, 21 tests — all passing). Pure helpers `parse_version` / `compare_versions` / `version_in_range` / `evaluate_criterion` / `assign_confidence` hold the comparison logic; `CpeMatcher` is the DB-backed pipeline (normalize via `vendor_aliases` → read `cve_cpe_match` → evaluate version → write resolved CPE back to `cpe_match_cache`). Confidence tiers and the `needs_review`-on-parse-failure bias are implemented as specified. Phase 5's regression harness plugs into `CpeMatcher.match()`.

1. New `services/cpe_matcher.py`. Reference `cve-bin-tool` / `vulnerablecode` semantics before writing version-range comparison. Pipeline:
   - Normalize software name (reuse `vendor_aliases`).
   - Resolve to CPE via `cpe_match_cache`; on miss, query `cve_cpe_match` / NVD and write back to `cpe_match_cache`.
   - Evaluate the asset_software `version` against the CPE version ranges from Phase 1.
2. Confidence assignment: `high` (exact CPE or exact vendor/product/version), `medium` (normalized name + version-in-range, CPE inferred), `low` (name-only/fuzzy), `needs_review`.
3. Version comparison must handle messy real-world versions (`124.0.0`, `20.11.1`, epochs, `-rc`). Use a defensive semver-ish comparator; default to `needs_review` on parse failure rather than guessing.
- **Verification:** unit tests per confidence tier; this is where the Phase 5 regression harness plugs in.
- **Risk:** **false positives destroy trust permanently** (roadmap principle). Bias toward `needs_review` over a wrong `high`.

### Phase 3 — Persist asset_findings + per-finding risk scorer + status workflow (data + service) — ✅ implemented 2026-06-12
*Depends on Phase 2 output shape.*

> Delivered: migration `046` (`asset_findings` table + `assets.asset_criticality`), `db/asset_finding.py`, `repositories/asset_findings.py` (upsert/prune via `replace_for_asset`, preserving reviewer status across recompute), `services/risk_scorer.py` (per-finding scorer, `needs_review` confidence forces the `Needs Review` tier), and `services/asset_findings_service.py` (CpeMatcher → score → persist; the unit Phase 4's job will call). `GET /assets/{id}/findings` now reads `asset_findings` (lazy-computes when empty, `?refresh=true` to force) and a new `PATCH /assets/{id}/findings/{finding_id}/status` drives the `open|accepted_risk|false_positive|in_progress|fixed` workflow. Tests in `tests/test_risk_scorer.py`.

1. **Migration 046** — `asset_findings` table per the roadmap data model: `org_id`, `asset_id`, `asset_software_id`, `cve_id`, `source`, `cvss_score`, `epss_score`, `kev_flag`, `severity`, `risk_score`, `match_confidence`, `status` (`open|accepted_risk|false_positive|in_progress|fixed`), `false_positive_reported_by`, `remediation_summary`, timestamps. (Decide: extend existing `finding_statuses` vs. new table — recommend **new table** since `finding_statuses` is keyed differently; cross-link by stable key.)
2. `repositories/asset_findings.py` following the established repo pattern (`SqlAssetSoftwareRepository` shape, `Depends(get_session)` factory).
3. New `services/risk_scorer.py` (per-finding, distinct from org-level `risk_scoring.py`): combine KEV (very high) + CVSS + EPSS + internet-exposed port + asset criticality + exploit recency, with **match_confidence as a required modifier**. Output `Critical|High|Medium|Low|Needs Review`.
4. Replace the in-memory matching in `inventory.py::GET /assets/{id}/findings` with reads from `asset_findings`.
5. Add `asset_criticality` field to `assets` (low difficulty) and remediation-summary templates.
- **Verification:** an uploaded inventory produces persisted findings with confidence + risk tier; status transitions persist.

### Phase 4 — Background matching job + wire M365 (worker layer) — ✅ implemented 2026-06-12
*Depends on Phases 2+3.*

> Delivered: `backend/app/workers/matcher_job.py` (`run_matcher_for_org` — advisory-lock-guarded via the per-org key `matcher_org_{id}`, opens its own session so it survives past the request; `run_matcher_sweep` — finds orgs whose latest succeeded `scan_run` is newer than their `asset_findings` and recomputes each). A nightly sweep job is registered in `scheduler.py` behind the new `MATCHER_SCHEDULE` setting (default `30 2 * * *`, after EPSS). CSV import (`inventory.py`) and M365 sync (`integrations.py`) fire `run_matcher_for_org` via `asyncio.create_task` on success. Tests in `tests/test_matcher_job.py` (+ `test_scheduler.py` coverage for the sweep job).
>
> **✅ #124 closed (2026-06-13).** M365 `sync_devices` now persists devices as `assets` under a `scan_run` (`source="m365"`) via the shared CSV upsert path (`commit_inventory` parameterized with `source`), then triggers the matcher. The endpoint returns `scan_run_id`; a sync that lists devices but fails persistence degrades to `status="partial"` rather than failing the call. Test coverage extended in `tests/test_m365_integration.py` (asserts 2 assets with `discovered_via="m365"` + a succeeded `m365` scan_run). **Remaining enhancement (not a gap):** devices carry no installed-software list from the basic Graph `managedDevices` call, so only assets (not `asset_software`) are created — software-level discovery via Graph `detectedApps` is a future add.

1. Add a matcher job to APScheduler following the `INGEST_SCHEDULE_*` pattern (`scheduler.py:28-34`, `_dispatch_ingestor`): on new `scan_run`, run the matcher and write `asset_findings`. Reuse the advisory-lock pattern (`try_acquire_lock`) so concurrent runs serialize.
2. Trigger matching at the end of CSV import **and** M365 sync (closes #124 — both already create `scan_runs` rows).
- **Verification:** uploading a CSV or syncing M365 auto-populates findings without a manual trigger.

### Phase 5 — Matcher regression harness + nightly CI (QA, parallelizable) — ✅ implemented 2026-06-12
*Owner suggestion: QA/testing. Start once Phase 2 has a callable matcher.*

> Delivered: `backend/tests/regression/matcher_known_good.py` (51 `(vendor, product, version) → expected_cve_set` cases drawn from real KEV/NVD CVEs — Log4Shell, Heartbleed, Struts, Spring4Shell, Citrix/FortiOS, etc. — spanning all five tiers: `high`/`medium`/`low`/`needs_review`/negative). The harness drives `CpeMatcher.match()` through an in-memory criteria catalog via a fake session (no DB, runs in <1s) and computes a `CalibrationReport` enforcing the gate. `backend/tests/regression/test_matcher_known_good.py` asserts the gate in pytest (one case per finding + the aggregate). A nightly GitHub Actions workflow (`.github/workflows/matcher-regression.yml`, `cron 15 7 * * *`, also `workflow_dispatch` + path-filtered on PRs touching the matcher) runs the suite and prints the calibration report. Current baseline: **51 cases, 54/54 tests pass (100%), 0 high-confidence false positives** (re-verified locally 2026-06-13 — `pytest tests/regression/` green; calibration gate satisfied).
>
> **⚠️ Scope of the gate (clarified 2026-06-13 review).** The harness feeds a hand-curated in-memory criteria catalog through a fake session, so it validates the **version comparator + confidence assignment** — NOT the production DB pipeline. It does **not** exercise the real `_fetch_criteria` SQL, the `vendor_aliases` lookup, the `cpe_match_cache` write-back, or the empty-`cve_cpe_match` state (the realistic not-yet-backfilled case). A green gate therefore does not by itself prove production matching works. That gap is now covered by `tests/test_cpe_matcher_integration.py`, which persists criteria via the real NVD parser and drives `CpeMatcher.match()` through real SQL (empty-table → `[]`, in-range → finding, write-back → `cpe_match_cache`). Treat the 51-case harness as a comparator-calibration gate, not end-to-end validation.

1. `backend/tests/regression/matcher_known_good.py` — 50+ `(vendor, product, version) → expected_cve_set` cases drawn from real KEV/NVD entries, spanning all confidence tiers.
2. Assert calibration gate: **≥95% pass**, **<2% high-confidence false-positive rate**.
3. Add a **nightly** (scheduled) job to `ci.yml` running the regression set and failing on drift (CI currently only runs on push/PR).
- **Verification:** regression suite green at the calibration target; nightly job visible in Actions.

### Phase 6 — Findings UI: confidence display + false-positive feedback (frontend, parallelizable) — ✅ implemented 2026-06-13
*Owner suggestion: frontend/UX. Start once Phase 3 endpoints exist.*

> Delivered in `frontend/src/pages/AssetsPage.tsx` + `frontend/src/api/assets.ts`. All three requirements met: (1) `ConfidenceChip` (`CONFIDENCE_META`) renders match-confidence chips with `low`/`needs_review` visually de-emphasized (muted color, dashed border, row opacity/strikethrough); (2) a "Report false positive" button calls `patchAssetFindingStatus()` → `PATCH .../findings/{id}/status`, with an Undo affordance, driving the 5-state workflow; (3) `RiskTierChip` (`TIER_COLORS`) shows the per-finding risk tier and a Remediation section renders `remediation_summary` in the asset drill-down. `assets.ts` exports `MatchConfidence`/`FindingStatus` types and the findings type carries `match_confidence`, `risk_score`, `risk_tier`, `remediation_summary`. ✅ Vitest added (2026-06-13): `src/api/__tests__/assets.findings.test.ts` covers `getAssetFindings` (URL + `?refresh=true`) and `patchAssetFindingStatus` (PATCH URL/body, error propagation).

1. Surface `match_confidence` prominently on findings (chip pattern like severity in `NvdTable.tsx`); visually **de-emphasize `low`/`needs_review`**.
2. "Report false positive" button on each finding → writes `asset_findings.false_positive_reported_by` and flips status. New `api/findings.ts` call.
3. Show per-finding risk tier + remediation summary in the asset drill-down (`AssetsPage.tsx` modal / `FindingsTab.tsx`).
- **Verification:** reviewer can see why a finding is high/low confidence and flag a false positive in one click.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| High-confidence false positive erodes trust permanently | Regression gate (Phase 5) blocks merge; bias to `needs_review`; de-emphasize low tiers in UI |
| NVD rate limits throttle CPE backfill | Cache in `cpe_match_cache`; incremental nightly pulls; honor existing 429 backoff |
| Messy version strings break range comparison | Defensive comparator; default to `needs_review` on parse failure |
| Duplicate/competing risk scorers (org-level vs per-finding) | Name the new one `risk_scorer.py`, keep `risk_scoring.py` untouched; document the split |
| Migration drift on a head already at 044 | Start at 045; CI `alembic check` already guards drift |
| Concurrent matcher runs on same org | Reuse `try_acquire_lock` advisory-lock pattern |

## Test plan

- Unit: CPE criteria parser (P1), version comparator + confidence assignment (P2), risk scorer factors (P3).
- Integration: CSV/M365 import → matcher job → persisted findings → API response (P3/P4).
- Regression: `matcher_known_good.py` at the calibration gate (P5), run nightly.
- Manual: a `manual_test_month3.md` smoke script mirroring `manual_test_month2.md`.

## What's left to implement (updated 2026-06-13)

The three code/QA gaps below were **closed on 2026-06-13** (kept here for the audit trail):

1. ~~**[Blocker for gate] Backfill CPE criteria for the existing CVE corpus.**~~ ✅ **Done** — `workers/cpe_backfill_job.py` + nightly `NVD_CPE_BACKFILL_SCHEDULE` job + `POST /ingest/cpe-backfill` admin route. Run the admin route until `persisted=0` to seed the initial corpus. *Note: the regression harness still uses an in-memory criteria catalog, so it does not exercise the empty-table state — the manual smoke test (step 1) covers that.*
2. ~~**[Carryover #124] M365 sync → assets/scan_runs persistence.**~~ ✅ **Done** — `sync_devices` upserts devices as assets under an `m365` scan_run via the shared `commit_inventory` path.
3. ~~**[QA] `docs/manual_test_month3.md` smoke script.**~~ ✅ **Done** — [manual_test_month3.md](manual_test_month3.md) written.
4. ~~**[QA, minor] Vitest coverage** for the findings API/UI.~~ ✅ **Done** — `src/api/__tests__/assets.findings.test.ts`.

### Review fixes applied (2026-06-13 senior review)

A code review of the PR surfaced issues now fixed on the branch:

- **Reviewer decisions survive software re-key.** `asset_findings` gained denormalized `software_vendor`/`software_product` (migration `047`); `replace_for_asset` re-associates a reviewer's `status`/false-positive verdict to the new row by the stable `(software_vendor, software_product, cve_id)` identity instead of the churning `asset_software_id`. Covered by `tests/test_asset_findings_repo.py`.
- **No version-blind `high`.** `assign_confidence` now grants the exact-CPE `high` tier only when both the asset and criterion CPEs pin a concrete (non-wildcard) version; two wildcard CPEs that share only vendor/product stay `medium`. A regression case that previously encoded the buggy `high` was corrected.
- **Fire-and-forget matcher is no longer GC-eligible.** `trigger_matcher_async` keeps a strong task reference (CSV import + M365 sync use it) so an import-triggered run can't be collected mid-flight.
- **M365 partial sync is consistent.** `sync_devices` re-stamps `last_sync_status="partial"` when device persistence fails after the credential commit, so the stored status matches the response.
- **Real-SQL integration test added** (`tests/test_cpe_matcher_integration.py`) — see the Phase 5 scope note above.

Still open (not code gaps):

5. **[Process, not code] Go/no-go evidence:** ≥1 interviewee reviews sample findings and judges them useful (roadmap Checkpoint 2).
6. **[Hygiene] Commit & PR.** All Month 3 work is currently uncommitted on `feature/month3-cpe-matching-plan`.
7. **[Enhancement, not a gap] M365 software-level discovery** via Graph `detectedApps` — current sync persists devices as assets only, so M365-only orgs get asset inventory but no software-based findings yet.

## Month 3 go/no-go gate (from roadmap Checkpoint 2)

**Proceed to Month 4 only if:** regression ≥95%; high-confidence FP rate <2%; ≥1 interviewee judges sample findings useful. Otherwise spend Month 4 hardening the matcher instead of starting the scanner.

## Recommended phase ordering summary

```
Phase 0 ✅ ─▶ Phase 1 ✅ ─▶ Phase 2 ✅ ─┬─▶ Phase 3 ✅ ─▶ Phase 4 ✅ (jobs/M365)
   (gate)     (CPE data)    (matcher)   ├─▶ Phase 5 ✅ (regression+nightly CI)
                                         └─▶ Phase 6 ✅ (UI)

✅ = code-complete, tests green. Prior P1/P4 gaps (backfill, M365 persistence)
     closed 2026-06-13. Only process items remain (go/no-go interview, commit/PR).
```
