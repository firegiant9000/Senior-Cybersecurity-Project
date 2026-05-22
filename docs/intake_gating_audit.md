# Intake Gating Audit — Phase B1

Output of the [Phase B1 spike](month_2_execution_plan.md#phase-b--onboarding-collapse).
Lists every coupling between assessment-intake completion and downstream
features so the rest of Phase B (decoupling, skip buttons, fast-path
landing) can move with eyes open.

Updated: 2026-05-21. Reflects the codebase at the start of Phase B work
(after PR #164 / commit `79f61ad`).

---

## Tier ladder (current)

Defined in [backend/app/services/assessment_intake.py](../backend/app/services/assessment_intake.py).

| Tier            | Requirements                                                                                                        |
|-----------------|----------------------------------------------------------------------------------------------------------------------|
| `INCOMPLETE`    | None met.                                                                                                             |
| `BASIC`         | `name`, `industry_label`, `primary_state`, `employee_range` (all four required).                                     |
| `ENHANCED`      | All BASIC + `vendors ≥ 1`, `domains ≥ 1`, `security_controls` started (≥ 1 answered).                                |
| `COMPREHENSIVE` | All ENHANCED + `revenue_range`, `compliance_frameworks ≥ 1`, `data_types ≥ 1`, `uploads ≥ 1`, `security_controls ≥ 8`. |

**Tier is computed live** in `evaluate_intake_snapshot()`. No tier value is
persisted on the org row — every read recomputes from the org + counts.

## Hard couplings between intake completion and features

These are the places where intake state directly gates a downstream feature.
Anything in this list has to be re-thought before the "useful dashboard
with only name + domain" wedge can ship.

### Backend

| # | Site                                                                                                                                                                                       | Coupling                                                                                                                                                | Notes                                                                                                                                          |
|---|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | [organizations.py:385](../backend/app/api/routes/v1/organizations.py#L385) — `GET /mine/findings`                                                                                          | Returns 409 unless `intake.current_tier not in ("incomplete", "basic")`. Findings report requires ENHANCED.                                              | Phase B keeps this gate but the tier ladder underneath changes — findings still require vendors + domains + controls, just labelled differently. |
| 2 | [organizations.py:513](../backend/app/api/routes/v1/organizations.py#L513) — `GET /mine/ai-summary`                                                                                        | Same ENHANCED gate as findings.                                                                                                                          | Same as above.                                                                                                                                  |
| 3 | [organizations.py:163](../backend/app/api/routes/v1/organizations.py#L163) — `GET /mine/intake`                                                                                            | Requires `get_current_org` (any org membership). Surfaces tier + `fields_to_advance` to the frontend.                                                    | Stays — but the tier definitions it returns are restructured in B2.                                                                            |
| 4 | [organizations.py:147](../backend/app/api/routes/v1/organizations.py#L147) — `GET /mine/readiness`                                                                                         | Maps intake tier → legacy {minimal, good, comprehensive}. Used by older UI surfaces.                                                                     | Mapping in `assessment_readiness.py:_TIER_TO_LEGACY` — re-check after B2 lands.                                                                |
| 5 | [organizations.py (PUT /{org_id})](../backend/app/api/routes/v1/organizations.py)                                                                                                          | Accepts `OrganizationUpdate` with all-optional fields, but the underlying ORM (`organizations.industry_label`, `ic3_sector`, `primary_state`, `employee_range`) is NOT NULL. | **Schema-level coupling**: an org *cannot exist* without these four fields. Migration in B2 (`037_make_org_intake_fields_nullable`) lifts this.   |
| 6 | [onboarding.py:25](../backend/app/api/routes/v1/onboarding.py#L25) — `POST /onboarding/complete`                                                                                            | Same NOT-NULL constraint hits here on org creation. `OrganizationCreate` schema requires `industry_label`, `primary_state`, `employee_range`.            | Loosened in B2 alongside the migration.                                                                                                         |
| 7 | [assessment_debug.py:33](../backend/app/services/assessment_debug.py#L33)                                                                                                                  | Drives the `findings_readiness` block of the debug snapshot.                                                                                            | Cosmetic — moves with the tier ladder change.                                                                                                   |

### Frontend

| # | Site                                                                                                                                                  | Coupling                                                                                                                                                       | Notes                                                                                                          |
|---|-------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| 8 | [ProtectedRoute.tsx](../frontend/src/components/ProtectedRoute.tsx)                                                                                   | Any authenticated route with `requireOrg=true` redirects to `/onboarding` when `orgId == null`.                                                                | Stays; the redirect destination just renders a much shorter wizard after B3/B4.                                |
| 9 | [AssessmentIntakePage.tsx](../frontend/src/pages/AssessmentIntakePage.tsx)                                                                            | The wizard requires the user to traverse 5 steps; `canAdvanceFromStep()` blocks "Next" until required fields are filled. No skip path exists today.            | B3 adds per-step skip buttons + persists which steps were skipped.                                             |
| 10 | [App.tsx routes](../frontend/src/App.tsx)                                                                                                            | New users land on `/dashboard` → `RootRoute` → `/onboarding` chain. There is no "skip to dashboard" door.                                                      | After B4 the dashboard renders for orgs that exist with only name+domain — no chain bounce.                    |
| 11 | [AssessmentBanner.tsx](../frontend/src/components/shared/AssessmentBanner.tsx) / [TierProgress.tsx](../frontend/src/components/shared/TierProgress.tsx) | Render "complete your intake" prompts based on `current_tier`.                                                                                                  | Cosmetic; copy update during B6 to use delta language instead of binary-gating language.                       |
| 12 | [IntakeProgressIndicator.tsx](../frontend/src/components/shared/IntakeProgressIndicator.tsx)                                                          | Shows the wizard sidebar tier progress + tier-unlocked toast.                                                                                                  | B6 swaps "you reached X" toast for "do Y to unlock Z" delta-style copy.                                        |

## Soft couplings (UI/copy only)

These reference the tier or unlock list but don't gate any functionality —
no behavioral change is required, only copy refresh once B2 changes the
tier definitions.

- [ProgressSummary.tsx](../frontend/src/components/shared/ProgressSummary.tsx) — step-5 review panel.
- [TierProgress.tsx](../frontend/src/components/shared/TierProgress.tsx) — generic tier-progress widget.
- Findings-snapshot model persists `assessment_tier` for historical reads only; no gating.

## Schema-level constraints to lift in B2

Migration `v037_make_org_intake_fields_nullable.py`:

1. `organizations.industry_label` → `NULL`able.
2. `organizations.ic3_sector` → `NULL`able.
3. `organizations.primary_state` → `NULL`able.
4. `organizations.employee_range` → `NULL`able.
5. Add `organizations.intake_skipped_steps JSONB NULL` (list of step keys
   the user dismissed) — persists across logins so the wizard doesn't
   re-pop the wall (R9 mitigation).
6. Add `organizations.intake_completed_at TIMESTAMPTZ NULL` (set by
   `/intake/complete`).

`OrganizationCreate` / `OrganizationUpdate` Pydantic schemas need
matching nullability. The `ic3_sector` post-validator becomes conditional
on `industry_label` being present.

## New tier ladder proposed for B2

Replaces the current ladder. Inventory and integration signals are now
first-class so a CSV-only or M365-only org reaches BASIC without ever
filling the demographic fields.

| Tier            | Requirements                                                                                                                                                                                                                                                                                                |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `BASIC`         | `name` **AND** at least one signal: `primary_domain` set, `domains ≥ 1`, `vendors ≥ 1`, `assets ≥ 1`.                                                                                                                                                                                                       |
| `ENHANCED`      | BASIC + `industry_label`, `primary_state`, `employee_range`, `security_controls` started.                                                                                                                                                                                                                    |
| `COMPREHENSIVE` | ENHANCED + `revenue_range`, `compliance_frameworks ≥ 1`, `data_types ≥ 1`, `uploads ≥ 1`, `security_controls_depth ≥ 8`.                                                                                                                                                                                     |

The "any of N signals" check on BASIC is the wedge — it means a user who
arrives via the M365 connect button or via a CSV upload gets a working
dashboard without ever opening the assessment wizard.

## Risks called out by this audit

- **R-A1**: Existing orgs in prod have all four demographic fields filled
  (they had to, NOT NULL). The migration is backward-compatible because
  it only widens nullability. No data backfill needed.
- **R-A2**: `_TIER_TO_LEGACY` mapping in `assessment_readiness.py` still
  maps BASIC → "minimal". After B2, BASIC is genuinely useful, so the
  legacy mapping is misleading. Either re-map BASIC → "good" or
  deprecate the readiness endpoint.
- **R-A3**: Frontend `useIntakePreview` hits `POST /mine/intake-preview`
  with optimistic vendor+domain counts. The B2 ladder change preserves
  this contract — the optimistic bump still wins via `max()` in
  `evaluate_intake_preview()`.
- **R-A4**: `industry_label` drives `LossProjectionService` (loss
  projection needs an IC3 sector). With B2's nullable industry, the
  service has to handle a missing sector — return a placeholder
  projection labelled "set industry to refine" rather than 500.

## Files in scope for Phase B (sourced from this audit)

Backend
- `backend/app/db/versions/037_make_org_intake_fields_nullable.py` (new)
- `backend/app/db/organization.py`
- `backend/app/schemas/organization.py`
- `backend/app/schemas/assessment_intake.py`
- `backend/app/services/assessment_intake.py`
- `backend/app/services/assessment_readiness.py`
- `backend/app/api/routes/v1/organizations.py` (skip + complete endpoints)
- `backend/app/api/routes/v1/onboarding.py`
- `backend/tests/test_assessment_intake_preview.py`
- `backend/tests/test_assessment_intake_skip.py` (new)

Frontend
- `frontend/src/pages/AssessmentIntakePage.tsx`
- `frontend/src/components/shared/IntakeProgressIndicator.tsx`
- `frontend/src/components/dashboard/NextStepsCard.tsx` (new)
- `frontend/src/api/assessmentIntake.ts`
- `frontend/src/types/assessmentIntake.ts`
- `frontend/src/pages/__tests__/AssessmentIntakePage.test.tsx`
