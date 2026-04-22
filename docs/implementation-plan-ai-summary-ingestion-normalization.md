# Implementation Plan: AI Summary UI, Ingestion Visibility, Normalization Layer

**Issues:** AI Executive Summary UI · Ingestion Failure Visibility · Normalization/Mapping Layer  
**Date:** 2026-04-20 · **Last audited:** 2026-04-20  
**Author:** Arlo Kharod  
**Branch base:** main (latest: `39c8e3a`)  
**Last migration:** `022_enable_pg_trgm.py`

---

## Implementation Status

Audited against current codebase. Legend: `DONE` · `PARTIAL` · `TODO` · `BUG`

| Task | Status | Notes |
|------|--------|-------|
| **M1** — Migration 021: normalization_log table | `DONE` | Idempotent, all columns and indexes present |
| **M2** — Migration 022: pg_trgm + GIN indexes | `DONE` | Extension + indexes on kev.vendor and org_vendors.vendor_name |
| **3C** — Normalization logging in routes | `DONE` | vendors (whitespace), domains (pattern), orgs (exact) — fire-and-forget |
| **3D** — Fuzzy vendor matching in KEV | `DONE` | Two-pass, threshold 0.75, match_confidence on Finding schema |
| **3E** — Industry mapping expansion (backend) | `DONE` | All 6 new labels + IC3 sector mappings in enums.py |
| **3F-be** — Vendor suggestion endpoint | `DONE` | GET /vendors/suggest, similarity > 0.4, 5 results, 30/min rate limit |
| **2A** — last_successful_run_at + consecutive_failures | `DONE` | Computed in /freshness handler, in SourceFreshness schema |
| **2B** — Populate next_scheduled_at | `DONE` | Set at IngestRun creation from APScheduler.get_job() |
| **2C** — Retry and cancel endpoints | `DONE` | POST /runs/{id}/retry and /cancel, both admin-only |
| **2D** — Health endpoint | `DONE` | GET /ingest/health, no auth, DB-based staleness per source |
| **1A** — Gemini JSON mode + StructuredSummary | `DONE` | Cache key bumped to v2, JSON mode on, parsing + fallback in place |
| **1B** — Frontend structured AI components | `DONE` | Posture/risks/gaps/actions inline in AISummaryTab; history section present |
| **2E** — PipelineHealthTab additions | `DONE` | All fields, retry/cancel buttons, visibilitychange wired |
| **3E-fe** — Industry dropdown (OnboardingPage) | `DONE` | All 14 options present |
| **3E-fe** — Industry dropdown (OrgProfilePage) | `DONE` | Industry `<select>` added; state synced from org; included in save body |
| **3F-fe** — Vendor typeahead UI | `DONE` | Debounced 300ms, calls /vendors/suggest, confidence shown |
| **output_format DB column** | `DONE` | Migration 023 added; ORM, schema, and repo.create() all threaded through |
| **require_role("member") on GET /mine/ai-summary** | `DONE` | Explicit role guard added to organizations.py |

### What remains

All planned items are complete. Outstanding work is test coverage only — see [Test Coverage Gaps](#test-coverage-gaps).

### Issues found and resolved

**BUG (fixed) — `output_format` computed but never stored**
- Added migration 023 (`backend/app/db/versions/023_add_output_format_to_ai_summary_generations.py`) — `VARCHAR(10)` column with `server_default='prose'`
- Added `output_format` to ORM model (`backend/app/db/ai_summary_generation.py`)
- Added `output_format` to `AISummaryGenerationListItem` schema (`backend/app/schemas/ai_summary_generation.py`)
- Threaded `output_format=output_format` into `repo.create()` in `backend/app/services/ai_summary.py`

**BUG (fixed) — cache served stale prose after JSON mode switch**
- Added `_CACHE_VERSION = "v2"` and `_cache_key(org_id)` helper in `backend/app/services/ai_summary.py`
- `_get_cached`, `_set_cache`, and `invalidate` all use the versioned key — old prose entries are never returned

**GAP (fixed) — OrgProfilePage had no industry edit surface**
- Added `INDUSTRY_OPTIONS` constant and `industryLabelField` state to `frontend/src/pages/OrgProfilePage.tsx`
- Synced from `organization.industry_label` in the existing `useEffect`
- Included `industry_label` in the company profile PUT body
- Added `<select>` field between Domain and Save button in the Company Profile form

**GAP (fixed) — AI summary route missing explicit role guard**
- `GET /mine/ai-summary` now uses `Depends(require_role("member"))` instead of `Depends(get_current_user)`

**GAP (open) — No test coverage for new paths**
- None of the new items (fuzzy matching, normalization log, health endpoint, retry/cancel, structured AI response) have tests
- See [Test Coverage Gaps](#test-coverage-gaps) below

---

## Table of Contents

1. [Implementation Status](#implementation-status)
2. [Dependency Graph](#dependency-graph)
3. [Stage Overview](#stage-overview)
4. [Stage 0 — Database Migrations](#stage-0--database-migrations)
5. [Stage 1 — Independent Backend](#stage-1--independent-backend)
6. [Stage 3 — AI Structured Response Backend](#stage-3--ai-structured-response-backend)
7. [Stage 4 — All Frontend](#stage-4--all-frontend)
8. [Issue Background: Current State and Gaps](#issue-background-current-state-and-gaps)
9. [Cross-Cutting Concerns](#cross-cutting-concerns)
10. [Critical Blockers](#critical-blockers)
11. [Test Coverage Gaps](#test-coverage-gaps)
12. [Risks Summary](#risks-summary)

---

## Dependency Graph

Each arrow means "must be complete before starting."  
Items on the same horizontal level with no arrows between them **can run in parallel**.

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 0: Migrations (ship first — nothing else can start)  │
│                                                             │
│   [M1] Migration 021: normalization_log table               │
│   [M2] Migration 022: pg_trgm extension + GIN indexes       │
│                                                             │
│   M1 and M2 are independent of each other (run together)   │
└─────────────────┬─────────────────────┬─────────────────────┘
                  │                     │
        ┌─────────▼──────────┐ ┌────────▼────────────────────────────────────┐
        │  M1 unblocks       │ │  M2 unblocks                                │
        │  [3C] Norm logging │ │  [3D] Fuzzy vendor matching                 │
        └─────────┬──────────┘ │  [3F-be] Vendor suggestion endpoint         │
                  │            └────────┬────────────────────────────────────┘
                  │                     │
┌─────────────────▼─────────────────────▼─────────────────────────────────────┐
│  STAGE 1: Independent Backend (all parallel, no inter-dependencies)          │
│                                                                              │
│  ── Needs M1 only ──    ── Needs M2 only ──    ── No migration needed ──    │
│  [3C] Norm logging      [3D] Fuzzy matching    [2A] Freshness improvements  │
│                         [3F-be] Suggestion     [2B] next_scheduled_at       │
│                                 endpoint       [2C] Retry/cancel endpoints  │
│                                                [2D] Health endpoint         │
│                                                [3E] Industry expansion      │
└────────────┬──────────────────┬────────────────────────┬────────────────────┘
             │                  │                         │
   ┌─────────▼────────┐  ┌──────▼──────────────┐  ┌──────▼───────────────┐
   │  STAGE 2         │  │  STAGE 3             │  │  STAGE 4             │
   │  (no new deps)   │  │  AI JSON mode        │  │  All Frontend        │
   │                  │  │                      │  │  (parallel streams)  │
   │  These were all  │  │  [1A] Gemini JSON    │  │                      │
   │  already in      │  │  mode + Structured   │  │  [1B] after 1A       │
   │  Stage 1 above   │  │  Summary schema      │  │  [2E] after 2A+2B+2C │
   │  (no Stage 2)    │  │                      │  │  [3F-fe] after 3F-be │
   └──────────────────┘  │  Soft dep: 3D done   │  │  [3E-fe] after 3E    │
                         │  first (match_conf   │  └──────────────────────┘
                         │  improves AI prompt) │
                         └──────────────────────┘
```

**Summary of hard dependencies:**

| Task | Requires |
|------|---------|
| 3C — Normalization logging | M1 (normalization_log table) |
| 3D — Fuzzy vendor matching | M2 (pg_trgm enabled) |
| 3F-be — Vendor suggestion endpoint | M2 (pg_trgm enabled) |
| 1A — Gemini JSON mode | None hard; 3D soft (richer findings → better prompt) |
| 1B — Frontend structured components | 1A |
| 2E — PipelineHealthTab additions | 2A + 2B + 2C |
| 3F-fe — Vendor typeahead UI | 3F-be |
| 3E-fe — Industry dropdown additions | 3E backend enum update |

**Fully independent (no dependencies on any other task):**
`2A`, `2B`, `2C`, `2D`, `3E`

---

## Stage Overview

| Stage | What | Parallel within stage? | Gate for |
|-------|------|----------------------|---------|
| **0** | DB migrations (M1, M2) | Yes — M1 and M2 are independent | Everything |
| **1** | All independent backend work | Yes — all tasks are independent | Stage 3, Stage 4 |
| **2** | (No distinct Stage 2 — all backend work fits Stage 1) | — | — |
| **3** | AI JSON mode backend (1A) | N/A — single task | Stage 4 (1B) |
| **4** | All frontend (1B, 2E, 3F-fe, 3E-fe) | Yes — each stream is independent | Ship |

> Stage 3 is kept separate because 1A has a soft ordering preference (ideally after 3D) and is the gate for the largest frontend deliverable (1B). Everything else in the backend can be developed concurrently in Stage 1.

---

## Stage 0 — Database Migrations

**Must ship before any other stage. Run migrations together in one deployment.**

### M1 — Migration 021: normalization_log table

New file: `backend/alembic/versions/021_add_normalization_log.py`

```sql
CREATE TABLE normalization_log (
  id               SERIAL PRIMARY KEY,
  org_id           INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
  data_type        VARCHAR(50) NOT NULL,     -- 'vendor' | 'domain' | 'industry'
  raw_value        TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  confidence       FLOAT NOT NULL DEFAULT 1.0,
  method           VARCHAR(50) NOT NULL,     -- 'exact' | 'whitespace' | 'pattern' | 'fuzzy' | 'alias'
  created_at       TIMESTAMP NOT NULL DEFAULT now(),
  created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX ix_normalization_log_org  ON normalization_log(org_id);
CREATE INDEX ix_normalization_log_type ON normalization_log(data_type);
```

New ORM + repository files:
- `backend/app/db/normalization_log.py`
- `backend/app/repositories/normalization_log_repo.py`

Unblocks: **3C**

---

### M2 — Migration 022: pg_trgm extension + GIN indexes

New file: `backend/alembic/versions/022_enable_pg_trgm.py`

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_kev_vendor_trgm        ON kev        USING GIN (vendor      gin_trgm_ops);
CREATE INDEX ix_org_vendor_name_trgm   ON org_vendors USING GIN (vendor_name gin_trgm_ops);
```

> pg_trgm ships with PostgreSQL 15 and is supported on Render managed Postgres. The `IF NOT EXISTS` guard makes this safe to re-run.  
> **Test locally with Docker before deploying.** GIN index builds on large tables can briefly lock writes.

Unblocks: **3D**, **3F-be**

---

## Stage 1 — Independent Backend

All tasks in this stage are independent of each other and can be assigned and developed in parallel. The only ordering constraint is that tasks needing M1 or M2 cannot be merged until those migrations are deployed.

---

### [3C] Normalization logging — requires M1

**Issue 3 · Files:** `backend/app/api/routes/v1/vendors.py`, `backend/app/api/routes/v1/domains.py`, `backend/app/api/routes/v1/organizations.py`

After each successful vendor create/update, domain add, or industry label change, write a row to `normalization_log` using the new `NormalizationLogRepo`:

```python
# Capture raw value BEFORE Pydantic strips it (compare pre/post validation)
await NormalizationLogRepo.write(
    org_id=org.id,
    data_type="vendor",        # or "domain" / "industry"
    raw_value=raw_input,
    normalized_value=stored,
    confidence=1.0,
    method="whitespace",       # or "pattern" / "exact"
    created_by=user.id
)
```

- Log writes must be fire-and-forget (`asyncio.create_task`) — do not block the user response.
- **No backfill** of existing records. Log only from this point forward.
- Vendor: `method="whitespace"`. Domain: `method="pattern"`. Industry: `method="exact"`, `normalized_value=ic3_sector`.

---

### [3D] Fuzzy vendor matching in KEV — requires M2

**Issue 3 · File:** `backend/app/services/vendor_alerts.py`

1. Keep the existing exact case-insensitive join as the **primary pass** (fastest, confidence=1.0).

2. Add a **second pass** only for org vendors that returned no exact match:
   ```sql
   SELECT kev.*, similarity(kev.vendor, org_vendor.vendor_name) AS score
   FROM kev, org_vendors
   WHERE org_vendors.org_id = :org_id
     AND similarity(kev.vendor, org_vendor.vendor_name) > 0.75
   ORDER BY score DESC
   ```
   Start at threshold **0.75** — lower only after auditing the first batch of matches.

3. Extend `Finding` schema (`backend/app/schemas/findings.py`) with `match_confidence: float | None = None`. Set 1.0 for exact matches, similarity score for fuzzy matches.

4. Pass confidence through `FindingsEngine → AISummaryService` so the AI prompt can note match quality.

5. Log each fuzzy match to `normalization_log` with `method="fuzzy"` and `confidence=<score>`.

> This task has a **soft ordering preference**: completing 3D before Stage 3 (1A) means the AI prompt will include richer, confidence-annotated findings. It is not a hard blocker for 1A.

---

### [3F-be] Vendor suggestion endpoint — requires M2

**Issue 3 · File:** `backend/app/api/routes/v1/vendors.py`

Add `GET /api/v1/vendors/suggest?q=<query>` — authenticated, member-level:

```python
SELECT vendor_name, similarity(vendor_name, :q) AS score
FROM technology_vendors
WHERE similarity(vendor_name, :q) > 0.4
ORDER BY score DESC
LIMIT 5
```

Returns `[{ "vendor_name": str, "score": float }]`.

- Apply title-case normalization to `vendor_name` in the response — NVD/CISA catalog names are lowercase (e.g., "microsoft corporation").
- Rate-limit to 30 req/min per user (same pattern as AI summary endpoint).

Unblocks: **3F-fe**

---

### [2A] Freshness improvements — no migration needed

**Issue 2 · File:** `backend/app/api/routes/v1/ingest.py`

In the `/freshness` handler, add two computed fields per source:

1. **`last_successful_run_at`** — most recent `IngestRun` row where `status='completed'` per source. Computed as a second subquery alongside the existing `last_run_at` query.

2. **`consecutive_failures: int`** — count of consecutive non-completed rows since the last `status='completed'` row per source. Compute in Python after the query (not SQL); keep it simple.

Add both to the `SourceFreshness` response schema.

No migration needed — reads from existing `ingest_runs` columns.

---

### [2B] Populate next_scheduled_at — no migration needed

**Issue 2 · File:** `backend/app/api/routes/v1/ingest.py` (`_run_ingestion()` function)

At the moment an `IngestRun` row is created, query APScheduler for the job's next fire time:

```python
job = scheduler.get_job(f"ingest_{source}")
run.next_scheduled_at = job.next_run_time if job else None
```

Column already exists since migration 016 — no schema change needed.

---

### [2C] Retry and cancel endpoints — no migration needed

**Issue 2 · File:** `backend/app/api/routes/v1/ingest.py`

**`POST /api/v1/ingest/runs/{run_id}/retry`** — admin-only
- Validate run exists and `status='failed'`
- Call `_run_ingestion(source, trigger="manual")` immediately
- Return new run id

**`POST /api/v1/ingest/runs/{run_id}/cancel`** — admin-only
- Validate run exists and `status='running'`
- Set `status='failed'`, `error_message='Manually cancelled'`, `finished_at=now()`
- **Known limitation:** does not stop the in-process `asyncio.create_task` — the underlying task continues until it finishes or errors. Include this in the response body as a `warning` field. A task registry fix is deferred.

---

### [2D] Health endpoint — no migration needed

**Issue 2 · File:** `backend/app/api/routes/v1/ingest.py`

`GET /api/v1/ingest/health` — **no auth required** (for Render health checks, UptimeRobot, etc.)

```json
{
  "healthy": true,
  "sources": {
    "nvd":       { "stale": false, "last_success_hours_ago": 4.2,  "consecutive_failures": 0 },
    "cisa_kev":  { "stale": true,  "last_success_hours_ago": 52.1, "consecutive_failures": 3 },
    "ic3":       { "stale": false, "last_success_hours_ago": 18.0, "consecutive_failures": 0 },
    "economics": { "stale": false, "last_success_hours_ago": 72.0, "consecutive_failures": 0 }
  }
}
```

Staleness thresholds (define in `config.py`):

| Source | Stale after |
|--------|------------|
| NVD | 25 hours |
| CISA KEV | 25 hours |
| IC3 | 168 hours (7 days) |
| Economics | 168 hours (7 days) |

`healthy: false` if any source is stale or has `consecutive_failures >= 2`.

> Read all values from the DB (`last_successful_run_at` subquery), **not** from APScheduler in-memory state. This keeps the endpoint accurate on multi-instance deployments.

---

### [3E] Industry mapping expansion — no migration needed

**Issue 3 · Files:** `backend/app/db/enums.py`, `frontend/src/pages/OnboardingPage.tsx`, `frontend/src/pages/OrgProfilePage.tsx`

**Backend:**
1. Add to `IndustryLabel` enum: `REAL_ESTATE`, `CONSTRUCTION`, `LEGAL_SERVICES`, `TRANSPORTATION`, `HOSPITALITY`, `NON_PROFIT`
2. Add to `INDUSTRY_TO_IC3_SECTOR` mapping: map each to its IC3 sector counterpart
3. No DB migration — `industry_label` is `VARCHAR(100)`, not a DB enum

**Frontend (can be done simultaneously with backend change):**
1. Add the 6 new labels to industry dropdowns in `OnboardingPage.tsx` and `OrgProfilePage.tsx`
2. Verify Pydantic schema and any frontend validation accepts the new strings
3. Deploy backend and frontend together to avoid a window where the frontend sends a value the backend rejects

---

## Stage 3 — AI Structured Response Backend

**Soft ordering:** Start this after 3D is merged. 3D adds `match_confidence` to findings, which can be referenced in the AI prompt for richer context. This is not a hard block — 1A is functional without 3D — but the quality of the output will be better.

---

### [1A] Gemini JSON mode + StructuredSummary schema

**Issue 1 · File:** `backend/app/services/ai_summary.py`

**Step 1 — Add response Pydantic models:**
```python
class RiskItem(BaseModel):
    title: str
    severity: str
    context: str

class GapItem(BaseModel):
    gap_type: str
    impact: str

class StepItem(BaseModel):
    priority: int
    action: str
    rationale: str

class StructuredSummary(BaseModel):
    narrative: str
    posture_statement: str
    notable_risks: list[RiskItem]
    data_gaps: list[GapItem]
    next_steps: list[StepItem]
```

**Step 2 — Enable JSON mode on the Gemini call:**
```python
model = genai.GenerativeModel(
    settings.GEMINI_MODEL,
    generation_config={"response_mime_type": "application/json"}
)
response = model.generate_content(prompt)
```

**Step 3 — Add JSON schema instructions to the prompt** (append after the existing instructions block):
```
Respond ONLY with valid JSON matching this exact schema:
{"narrative": "...", "posture_statement": "...",
 "notable_risks": [{"title": "...", "severity": "...", "context": "..."}],
 "data_gaps": [{"gap_type": "...", "impact": "..."}],
 "next_steps": [{"priority": 1, "action": "...", "rationale": "..."}]}
```

**Step 4 — Add strip-fence pre-processor + safe JSON parse:**
```python
raw = response.text.strip()
if raw.startswith("```"):               # strip markdown code fences
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
try:
    parsed = StructuredSummary.model_validate_json(raw)
except (ValidationError, JSONDecodeError):
    # fall back: treat entire response as prose narrative only
    parsed = StructuredSummary(
        narrative=raw, posture_statement="", notable_risks=[], data_gaps=[], next_steps=[]
    )
```

**Step 5 — Extend `AISummaryResponse`** with optional structured fields (additive — no breaking change):
```python
posture_statement: str | None = None
notable_risks: list[RiskItem] | None = None
data_gaps: list[GapItem] | None = None
next_steps: list[StepItem] | None = None
```

**Step 6 — Template fallback** (`_build_fallback()`) stays prose-only; structured fields return `None`. Document in a comment.

**Token budget check:** Verify with 20-finding prompts that JSON output fits within Gemini 2.5 Flash output limits. If responses are truncated, reduce findings cap from 20 to 10 in the prompt builder.

**Cache key:** After deploying the new prompt, bump the cache key version (e.g., prefix with `v2:`) to avoid serving cached prose responses through the new structured handler.

**`output_text` format change:** After this change, `ai_summary_generations.output_text` will store JSON strings, not prose. The history endpoints return this field raw. Add `output_format: str` (`"prose"` | `"json"`) to `ai_summary_generations` in a follow-on migration (021 or 023), so history viewers can correctly parse the field. Until then, add `try: json.loads(output_text)` with prose fallback in any history UI.

Unblocks: **1B**

---

## Stage 4 — All Frontend

All four streams in this stage are independent of each other. Assign them in parallel once their backend counterparts (from Stage 1 or Stage 3) are merged and deployed.

---

### [1B] AI Summary structured UI — requires 1A

**Issue 1 · Files:** `frontend/src/components/tabs/AISummaryTab.tsx`, new component files

| Component | Data source | Gate |
|-----------|------------|------|
| `PostureGauge` | `risk_score`, `risk_label`, `posture_statement` | `data.posture_statement != null` |
| `NotableRisksCard` | `notable_risks[]` | `data.notable_risks != null` |
| `DataGapsWidget` | `data_gaps[]` | `data.data_gaps != null` |
| `ActionPlanCard` | `next_steps[]` | `data.next_steps != null` |

- If all four structured fields are null (template fallback or JSON parse failure), render the existing prose layout unchanged — no regression for non-Gemini environments.
- Add `fetchAISummaryHistory()` to `frontend/src/api/` calling `/mine/ai-summary/history`. Add a collapsible "Past Summaries" section in `AISummaryTab` showing timestamp, model, and risk score per entry. Handle `output_text` as both prose and JSON (check for `output_format` field or attempt `JSON.parse`).

---

### [2E] PipelineHealthTab additions — requires 2A + 2B + 2C

**Issue 2 · File:** `frontend/src/components/tabs/PipelineHealthTab.tsx`

All changes are additive to the existing card layout:

1. Show `last_successful_run_at` on each source card, labeled distinctly from "last run"
2. Show `consecutive_failures` as a red badge ("Failed 3×") when value > 0
3. Show `next_scheduled_at` as a human-readable countdown ("Next run: in 4h")
4. Add **Retry** button per source card — shown only when `status='failed'`, calls `POST /runs/{id}/retry`, refreshes the card on response
5. Add **Cancel** button on `status='running'` cards older than 30 minutes — show the backend warning about in-process tasks in a tooltip
6. Verify `visibilitychange` event wiring correctly stops the 1-second polling loop when the tab is not visible

---

### [3F-fe] Vendor typeahead UI — requires 3F-be

**Issue 3 · File:** `frontend/src/pages/OrgProfilePage.tsx`

- Add a debounced typeahead input (fires after 2 characters) to the vendor add form
- Call `GET /api/v1/vendors/suggest?q=<input>` and show up to 5 suggestions as a dropdown
- Selecting a suggestion fills the vendor name field
- Show the suggestion's `score` as a subtle confidence indicator (e.g., "98% match") on hover

---

### [3E-fe] Industry dropdown additions — requires 3E backend

**Issue 3 · Files:** `frontend/src/pages/OnboardingPage.tsx`, `frontend/src/pages/OrgProfilePage.tsx`

(Described inline in Stage 1 under [3E] — deploy frontend changes together with the backend enum update to avoid a mismatch window.)

---

## Issue Background: Current State and Gaps

This section documents what exists today per issue for reference during implementation. The stages above are the implementation guide.

---

### Issue 1 — AI Executive Summary UI

**Goal:** Surface overall posture, notable risks, uncertainty/data gaps, and recommended next steps as structured, visually distinct sections — not embedded in a prose narrative.

**Current State (~80% complete as infrastructure)**

Gemini 2.5 Flash generates a single prose string (`narrative`) from a structured prompt that already instructs the model to cover posture, top findings, data gaps, and next steps. The response schema (`AISummaryResponse`) has no structured fields. The frontend renders the narrative as plain paragraphs with a risk score badge and feedback widget.

**Key files:**
- `backend/app/services/ai_summary.py` — Gemini call, caching, feedback loop, persistence
- `backend/app/api/routes/v1/organizations.py` (lines 270–400) — `/mine/ai-summary`, `/feedback`, `/history`, `/history/{id}`
- `frontend/src/components/tabs/AISummaryTab.tsx` — renders narrative + risk metric + feedback
- `frontend/src/api/` — `fetchAISummary()` and `submitFeedback()` exist; no history client

**What the backend returns today:**
```
narrative: str            # single unstructured block
ai_generated: bool
model_used: str | None
findings_count: int
risk_score: float
risk_label: str
generated_at: str
cached: bool
disclaimer: str
disclaimer_block: DisclaimerBlock | None
```

**Gaps:**
- No `posture_statement`, `notable_risks`, `data_gaps`, or `next_steps` fields on the response
- JSON mode not enabled in the Gemini call — code does `response.text` with no parsing
- No frontend components for posture gauge, risk cards, gap list, or action plan
- No UI for generation history (endpoint exists; no frontend)

**Known issues to address during implementation:**
- Token budget: JSON output is more verbose. Test whether 20-finding prompts fit. Reduce cap to 10 if needed.
- `output_text` in `ai_summary_generations` will change from prose to JSON — history viewers need to handle both.
- Gemini may still return prose wrapped in markdown code fences despite JSON mode — the strip-fence pre-processor handles this.
- Cache must be version-bumped after the prompt changes.

---

### Issue 2 — Ingestion Failure / Retry / Last-Run Visibility

**Goal:** Make scheduled ingestion jobs visible and diagnosable: distinguish last-run from last-success, expose the upcoming schedule, allow retry/cancel from the UI, and provide a health endpoint for external monitoring.

**Current State (solid infrastructure, specific observability gaps)**

APScheduler runs 4 cron jobs (NVD, CISA KEV, IC3, Economics). Each run writes an `IngestRun` record with `status`, `retry_count`, `skipped_reason`, `trigger`. Exponential backoff retry (up to `INGEST_MAX_RETRIES=2`) fires via `asyncio.create_task` — no DB record of the pending retry. `PipelineHealthTab` shows per-source cards with status, record counts, and run history. Admins can manually trigger ingestion.

**Key files:**
- `backend/app/workers/scheduler.py` — APScheduler init and cron registration
- `backend/app/api/routes/v1/ingest.py` — orchestration, retry logic, all 4 endpoints
- `backend/app/services/ingest_lock.py` — advisory locks, stale-run cleanup
- `backend/app/models/ingest_run.py` — `ingest_runs` table ORM
- `frontend/src/components/tabs/PipelineHealthTab.tsx` — admin dashboard (355 lines)

**Existing endpoints:**
```
GET  /api/v1/ingest/freshness    # viewer — latest run per source + total record counts
GET  /api/v1/ingest/runs         # viewer — paginated history with source/status filters
GET  /api/v1/ingest/schedule     # viewer — cron expressions + next fire times
POST /api/v1/ingest/trigger      # admin — manual trigger
```

**Gaps:**
- `last_successful_run_at` missing — freshness mixes last-run and last-success
- `consecutive_failures` not tracked — no way to see "failed 3 times in a row"
- `next_scheduled_at` column exists in `ingest_runs` (since migration 016) but is never populated
- Retry schedule is in-memory only — lost on app restart, invisible in UI
- No retry or cancel endpoints — admin must wait for backoff or restart
- No health endpoint for external monitoring

**Known issues to address:**
- Cancel endpoint marks the DB record as failed but cannot stop the underlying in-process `asyncio.create_task`. Document the limitation in the response body. A proper task registry fix is deferred.
- Health endpoint must read from DB (`last_successful_run_at`), not APScheduler memory, to be accurate on multi-instance deployments.
- Even after this work, exponential backoff retries remain in-memory. Full persistence requires a polling loop on startup. Deferred.

---

### Issue 3 — Normalization / Mapping Layer

**Goal:** Add an auditable layer tracking raw-to-normalized values for vendor names, domain names, and industry mappings. Add fuzzy vendor matching with confidence scores. Expand industry coverage. Add vendor suggestions at input time.

**Current State (minimal, one-directional normalization)**

Raw input is discarded after schema validation — no audit trail. KEV matching is exact case-insensitive only. Industry labels cover 9 categories but 6 IC3 sectors (Real Estate, Construction, Legal Services, Transportation, Hospitality, Non-Profit) have no frontend counterpart.

**Key files:**
- `backend/app/schemas/org_vendor.py` — whitespace-only vendor normalization via field validator
- `backend/app/schemas/org_domain.py` — lowercase + trailing-dot strip
- `backend/app/db/enums.py` — `INDUSTRY_TO_IC3_SECTOR` hardcoded dict (9 labels → 14 sectors, 6 gaps)
- `backend/app/services/vendor_alerts.py` (line 76) — case-insensitive exact KEV join
- `backend/app/db/org_vendor.py`, `backend/app/db/org_domain.py` — storage models

**Gaps:**
- No `normalization_log` table — no raw-vs-normalized history
- No fuzzy matching — "Microsoft Corporation" does not match "microsoft" in KEV
- No confidence scores on KEV matches
- 6 IC3 sectors with no frontend industry labels
- No vendor typeahead / "did you mean?" at input time

**Known issues to address:**
- `pg_trgm` is not enabled anywhere in migrations or docker-compose. Migration 022 is a hard prerequisite for 3D and 3F.
- Fuzzy match threshold of 0.75 will generate false positives. Audit first batch manually before lowering.
- Existing `org_vendors` records have no raw-value history. Log only new submissions — no backfill.
- Adding `match_confidence` to `Finding` schema touches every finding type. Run `test_findings_engine.py` and `test_findings_integration.py` in full after this change.
- New industry labels must be deployed backend + frontend together to avoid validation mismatch.

---

## Cross-Cutting Concerns

### 1. The three issues share a data pipeline

All three features are coupled through the findings pipeline. This is why deploying Issue 3 first makes Issue 1 better automatically:

```
OrgVendor.vendor_name
    ↓ (Issue 3: normalization + fuzzy matching)
VendorAlertService.get_alerts()  ← match_confidence attached to each finding
    ↓
FindingsEngine → FindingsSnapshot
    ↓ (Issue 2: data freshness — ensures findings are current)
AISummaryService → AISummaryResponse
    ↓ (Issue 1: structured UI shows posture, risks, gaps, actions)
AISummaryTab
```

### 2. Role guard inconsistency

Ingestion endpoints use explicit `require_role("viewer")` / `require_role("admin")`. The AI summary endpoint uses implicit membership (no explicit role guard). Normalize during this work:
- Add `require_role("member")` to `GET /mine/ai-summary`
- New normalization log exposure (if any) should be `require_role("admin")`

### 3. `output_text` format drift

`ai_summary_generations.output_text` stores prose today. After Stage 3 it stores JSON. Plan:
1. Add `output_format: str` (`"prose"` | `"json"`) column in a follow-on migration (can piggyback on 021 or be its own 023)
2. Until that column exists, add `try: json.loads(output_text)` with prose fallback in all history readers

### 4. Retry persistence gap (deferred)

Stage 1 makes retries visible and manually re-triggerable, but exponential backoff is still in-memory. Full fix requires a persistent job queue. Deferred — document clearly in cancel endpoint response.

### 5. No ingest → AI summary cache invalidation link

When a large NVD batch ingests, the 1-hour TTL AI summary cache may serve stale data for up to an hour. Acceptable for MVP. A post-ingest hook that selectively invalidates affected org caches is a follow-on optimization.

---

## Critical Blockers

| # | Blocker | Affects | Status | Resolution |
|---|---------|---------|--------|-----------|
| 1 | `pg_trgm` extension not enabled | 3D, 3F | **RESOLVED** — migration 022 deployed | — |
| 2 | Gemini JSON mode not enabled | 1A | **RESOLVED** — `response_mime_type` set, strip-fence and fallback in place | — |
| 3 | JSON parse failure on malformed Gemini response | 1A | **RESOLVED** — try/except on ValidationError + JSONDecodeError | — |
| 4 | `output_text` format changes after JSON mode | 1A, 1B | **RESOLVED** — migration 023 added column; ORM, schema, repo.create() all updated | — |
| 5 | Industry enum expansion must deploy both layers at once | 3E | **RESOLVED** — backend done, OnboardingPage done, OrgProfilePage selector added | — |
| 6 | Fuzzy match false positives at low threshold | 3D | **MITIGATED** — threshold set at 0.75, logged to normalization_log for audit | Audit first batch of fuzzy matches in prod |

---

## Test Coverage Gaps

All items below are for **shipped code** — these are untested paths in production today.

| Gap | Scope | File to create/extend |
|-----|-------|----------------------|
| Fuzzy vendor matching — no isolated unit tests | 3D (shipped) | Add `test_vendor_alerts.py`: exact match → confidence=1.0; fuzzy hit → confidence=0.75–0.99; no match → finding not generated |
| AI summary JSON parse path not tested | 1A (shipped) | Extend `test_ai_summary_generation.py`: JSON mode success; malformed JSON → prose fallback; missing structured fields → None |
| Retry and cancel endpoints not tested | 2C (shipped) | Add `test_ingest_control.py`: retry on failed run; retry rejects non-failed; cancel on running; cancel rejects non-running |
| Normalization log repo not tested | 3C (shipped) | Add `test_normalization_log.py`: write on vendor create; write on domain add; write on industry change; fire-and-forget doesn't block response |
| Health endpoint not tested | 2D (shipped) | Add to `test_ingest_freshness.py`: healthy=true when all fresh; healthy=false when any source stale; no auth required |
| `match_confidence` not asserted in existing findings tests | 3D (shipped) | Extend `test_findings_engine.py` with confidence assertions on vendor findings |
| No integration test: vendor → fuzzy KEV → AI summary | All 3 | New case in `test_findings_integration.py` |

---

## Risks Summary

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Gemini returns non-JSON despite JSON mode | Medium | Medium | Strip fences; Pydantic validate; fall back to prose |
| Fuzzy match introduces false-positive security findings | Medium | High | Conservative threshold (0.75+); log all fuzzy matches; audit first batch manually |
| pg_trgm migration fails on Render managed Postgres | Low | High | Test with Docker locally first; `IF NOT EXISTS` prevents re-run failures |
| Normalization log writes slow down vendor/domain submit | Low | Low | Use `asyncio.create_task` — fire and forget |
| Industry enum expansion breaks existing org profile validation | Low | Medium | Additive change; existing strings unchanged; deploy both layers together |
| Cancel endpoint misleads admins (underlying task still runs) | Medium | Low | Return explicit `warning` field in response body |
| AI summary cache serves stale data after large ingestion | Medium | Low | Acceptable for MVP; document as known gap |
| Token budget exceeded with JSON mode output | Medium | Medium | Test with 20-finding prompt; reduce cap to 10 if truncation occurs |
