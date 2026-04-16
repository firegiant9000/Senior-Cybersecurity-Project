# Implementation Plan: Assessment Validation Engine

**Author:** Arlo Kharod
**Date:** 2026-04-15 (last updated 2026-04-15)

> **Both issues are now fully implemented.** This document is retained as a reference for what was built and what deliberate trade-offs were made.

---

## Issue 1: Scheduled Ingestion — Complete ✅

All phases implemented. Tests added for lock contention, schedule registration, and retry logic.

| Component | File |
|-----------|------|
| Scheduling env vars (`INGEST_SCHEDULE_*`, `SCHEDULER_ENABLED`, etc.) | `backend/app/core/config.py` |
| `IngestRun` model extended (`trigger`, `retry_count`, `skipped_reason`, `next_scheduled_at`) | `backend/app/models/ingest_run.py` |
| Alembic migration for new columns | `backend/app/db/versions/016_extend_ingest_runs.py` |
| Schemas updated with new fields | `backend/app/schemas/ingest_run.py` |
| PG advisory locking (`try_acquire_lock`, `release_lock`, `expire_stale_runs`) | `backend/app/services/ingest_lock.py` |
| APScheduler integration with per-source cron jobs | `backend/app/workers/scheduler.py` |
| Scheduler wired into app lifespan | `backend/app/main.py` |
| `_run_ingestion` updated: locking + trigger param + retry with back-off | `backend/app/api/routes/v1/ingest.py` |
| `GET /api/v1/ingest/schedule` endpoint | `backend/app/api/routes/v1/ingest.py` |
| `app.models.ingest_run` added to `_import_all_orm_models` | `backend/app/db/engine.py` |
| `_ensure_ingest_run_columns` for non-migration installs | `backend/app/db/engine.py` |
| `apscheduler==3.10.4` added | `backend/requirements.txt` |
| Scheduling env vars documented | `.env.example` |
| Tests: lock acquire/contention/release, stale run expiry | `backend/tests/test_ingest_lock.py` |
| Tests: scheduler enabled/disabled, invalid/empty cron handling | `backend/tests/test_scheduler.py` |

**To activate scheduling:** set `INGEST_SCHEDULE_NVD`, `INGEST_SCHEDULE_KEV`, etc. in `.env` or Render env vars using standard 5-field cron syntax. Empty = disabled (current default).

---

## Issue 2: Assessment Validation Engine — Complete ✅

### What was built

| Phase | Component | File |
|-------|-----------|------|
| 1 | Validation engine (all rule categories) | `backend/app/services/assessment_validator.py` |
| 1 | Pydantic response schemas | `backend/app/schemas/assessment_validation.py` |
| 2 | `GET /api/v1/organizations/mine/validation` endpoint | `backend/app/api/routes/v1/organizations.py` |
| 3 | Vendor name normalization validators (trim + collapse whitespace) | `backend/app/schemas/org_vendor.py` |
| 3 | Domain name normalization validator (lowercase + trim) | `backend/app/schemas/org_domain.py` |
| 3 | CSV import duplicate detection within-file | `backend/app/api/routes/v1/vendors.py` (`_parse_csv_rows`) |
| 3 | Backfill migration — dedup + normalize existing vendor/domain rows | `backend/app/db/versions/017_normalize_vendor_domain_casing.py` |
| 4 | `ValidationPanel` frontend component | `frontend/src/components/ValidationPanel.tsx` |
| 4 | Validation API client | `frontend/src/api/assessmentValidation.ts` |
| 4 | `ValidationPanel` rendered on org profile page | `frontend/src/pages/OrgProfilePage.tsx` (line 564) |
| 4 | Client-side duplicate warning before vendor/domain API call | `frontend/src/pages/OrgProfilePage.tsx` (`handleAddVendor`, `handleAddDomain`) |
| 4 | CSV import preview (two-step: preview → confirm) | `frontend/src/pages/OrgProfilePage.tsx` + `frontend/src/api/vendors.ts` |
| 4 | `POST /organizations/{org_id}/vendors/import/preview` endpoint | `backend/app/api/routes/v1/vendors.py` |
| 4 | Preview response schema | `backend/app/schemas/org_vendor.py` (`OrgVendorImportPreviewResponse`) |
| 5 | Magic byte validation for binary uploads (PDF, ZIP, XLSX) | `backend/app/services/file_upload.py` |
| — | Unit tests (11 cases): rule categories, score math, edge cases | `backend/tests/test_assessment_validator.py` |
| — | Integration tests (3 cases): auth, no-org, response structure | `backend/tests/test_validation_endpoint.py` |

### Validation rules implemented

| Rule | Category | Severity |
|------|----------|----------|
| Missing org name / industry / state / employee range | `missing_field` | error |
| No vendors / no domains | `missing_field` | error |
| Missing revenue range | `missing_field` | warning |
| No security controls answered | `missing_field` | warning |
| No compliance frameworks | `missing_field` | info |
| No data types specified | `missing_field` | info |
| Case-duplicate vendors | `duplicate` | warning |
| Near-duplicate vendors (difflib ≥ 0.85 ratio) | `duplicate` | warning |
| Case-duplicate domains | `duplicate` | warning |
| Invalid domain format (legacy data) | `invalid_format` | error |
| Vendor name has extra whitespace | `invalid_format` | warning |
| HIPAA without health data type | `conflict` | warning |
| PCI-DSS without payment data type | `conflict` | warning |
| All security controls answered "unsure" | `quality` | warning |
| Only 1 vendor tracked | `quality` | info |
| No uploads | `quality` | info |

### Quality score

`score = 100 − (errors × 15) − (warnings × 5) − (infos × 1)`, floored at 0.

### Known deliberate trade-offs

- **No caching** on the validation endpoint — result is recomputed per request. Acceptable at current scale (< 200ms scoped to one org). Add ETag/cache-control if latency becomes a concern.
- **Near-duplicate check is O(n²)** per org, mitigated by early-exit on length difference > 3 and typical org vendor count < 100.
- **Conflict rules are a small curated set** (HIPAA, PCI-DSS). Additional frameworks can be added to `_COMPLIANCE_DATA_REQUIREMENTS` in `assessment_validator.py` without changing the engine.
- **Phase 5 magic byte check skips text types** (CSV, JSON, plain text) — no reliable signatures; content-type whitelist is the guard for those.
- **CSV preview `would_skip` count** reflects in-file duplicates only, not DB duplicates. DB duplicates are reported in the `errors` field of the actual import response.
