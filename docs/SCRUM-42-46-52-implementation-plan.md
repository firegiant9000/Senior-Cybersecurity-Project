# SCRUM-42, SCRUM-46, SCRUM-52 — Implementation Status & Plan

**Date:** 2026-04-11
**Author:** Arlo (via investigation)

---

## SCRUM-42 — Auth Pages & Protected Routing

**Assignee:** DJ | **Status:** In Testing

### What's Done

| Requirement | Status | Location |
|---|---|---|
| Login page (email/password + error handling + forgot password) | Done | `frontend/src/pages/LoginPage.tsx` |
| Signup (create account + email verification) | Done | Toggle inside LoginPage (not separate page) |
| `/login` route | Done | `frontend/src/App.tsx:14` |
| `/onboarding` route (protected, org-optional) | Done | `frontend/src/App.tsx:15-21` |
| `/settings` route (protected) | Done | `frontend/src/App.tsx:23-29` |
| `/` dashboard route (protected, wildcard) | Done | `frontend/src/App.tsx:31-37` |
| ProtectedRoute component | Done | `frontend/src/components/ProtectedRoute.tsx` |
| Header with auth UI (email, Settings, Logout) | Done | `frontend/src/components/dashboard/DashboardHeader.tsx` |
| Firebase Auth integration (AuthContext) | Done | `frontend/src/context/AuthContext.tsx` |
| fetchWithAuth (Bearer token, 401 redirect) | Done | `frontend/src/api/fetchWithAuth.ts` |

### What's Remaining

1. **No dedicated `/signup` route** — The ticket says "login and signup pages" (plural). Currently signup is a toggle within `/login`. Either:
   - Add a `/signup` route in `App.tsx` that renders `LoginPage` with a `defaultSignUp` prop, OR
   - Accept the combined page and close this as-is (team decision).
2. **Onboarding page has no logout escape** — A user stuck on `/onboarding` can't log out without manually navigating. Consider adding a logout link.

### Verdict

~95% complete. The only gap is the missing `/signup` route, which may be intentional (combined page). Confirm with the team whether a separate route is required before closing.

---

## SCRUM-46 — Dashboard.tsx TypeScript Exclusion Fix

**Assignee:** CK | **Status:** In Testing

### What's Done

| Requirement | Status | Notes |
|---|---|---|
| Dashboard.tsx has no type errors | Done | `frontend/src/Dashboard.tsx` is clean, strict TS |
| Build passes (`tsc && vite build`) | Done | Verified — no errors |
| CI type check passes (`npx tsc --noEmit`) | Done | `.github/workflows/ci.yml:97-98` |
| No `@ts-ignore` / `as any` workarounds | Done | None found in frontend/src/ |

### What's Remaining

1. **The exclusion is still in `tsconfig.json`** — `frontend/tsconfig.json:28` still has:
   ```json
   "exclude": ["src/pages/Dashboard.tsx"]
   ```
   The ticket explicitly says "remove from tsconfig.json exclude list." This line must be deleted.
2. **Verify build still passes after removal** — Since the actual Dashboard code is in `frontend/src/Dashboard.tsx` (re-exported by `frontend/src/pages/Dashboard.tsx`), removing the exclusion should be safe, but needs verification.
3. **Clean up `frontend/src/pages/Dashboard.tsx`** — This file is a 4-line re-export with ~650 lines of commented-out legacy code. The dead code should be removed.

### Implementation Steps

1. Remove `"exclude": ["src/pages/Dashboard.tsx"]` from `frontend/tsconfig.json:28`
2. Delete commented-out legacy code from `frontend/src/pages/Dashboard.tsx` (keep only the re-export)
3. Run `npm run build` and `npx tsc --noEmit` to verify
4. Push and confirm CI passes

### Verdict

~80% complete. The underlying type errors are fixed, but the literal task (remove the exclusion line) hasn't been done yet. This is a 5-minute fix.

---

## SCRUM-52 — Parameterized SMB Risk Scoring

**Assignee:** CK | **Status:** In Testing

### What's Done

| Component | Status | Location |
|---|---|---|
| `ATTACK_SECTOR_WEIGHTS` dictionary | Done | `backend/app/ingestors/ic3_real.py:32-200` (13 attack types, sector weights) |
| `get_sector_weights()` helper (fuzzy match) | Done | `backend/app/ingestors/ic3_real.py:220-229` |
| Organization model with `industry_label`, `ic3_sector`, `employee_range` | Done | `backend/app/db/organization.py` |
| EmployeeRange enum (SOLO through LARGE_ENTERPRISE) | Done | `backend/app/db/enums.py:56-62` |
| Employee range → incident rate mapping | Done | `backend/app/services/loss_projection.py:37-44` |
| Existing `calculate_risk_score()` (generic, CVE/KEV/IC3/econ) | Done | `backend/app/services/risk_scoring.py:6-50` |
| `/organizations/mine/` route infrastructure | Done | `backend/app/api/routes/v1/organizations.py` |
| Branch with partial work | Exists | `Risk-Scoring-and-fix-dashboard` branch (commits `7e37db3`, `121c306`) |

### What's Remaining

1. **`calculate_smb_risk_score()` function** — Does not exist yet. Needs to be created in `backend/app/services/risk_scoring.py`. Must:
   - Accept organization profile (industry, employee_range)
   - Use `ATTACK_SECTOR_WEIGHTS` for industry exposure weighting
   - Use `employee_range` for size factor
   - Return a transparent breakdown: overall score, industry contribution, size contribution, component details

2. **`GET /organizations/mine/risk` endpoint** — Does not exist. Add to `backend/app/api/routes/v1/organizations.py`. Existing sibling endpoints:
   - `/mine/executive-summary` (line 76)
   - `/mine/loss-projection` (line 90)
   - `/mine/vendor-alerts` (line 110)

3. **Response schema** — Need a Pydantic model (e.g., `RiskScoreResponse`) in `backend/app/schemas/`. Should include:
   - `score: float` (0-100)
   - `industry_exposure: dict` (sector, weight, contributing attack types)
   - `size_factor: dict` (employee_range, multiplier)
   - `breakdown: list` (component-level detail)
   - `methodology: str`

4. **Frontend API call** — Add fetch function to `frontend/src/api/` for the new endpoint.

5. **Frontend display** — Wire the risk score into the dashboard (likely `SmBAdvisorTab.tsx`).

6. **Tests** — Extend `backend/tests/test_risk_scoring.py` with unit tests for `calculate_smb_risk_score()`.

### Implementation Steps

**Phase 1 — Backend (core)**
1. Create `calculate_smb_risk_score()` in `backend/app/services/risk_scoring.py`
   - Import `ATTACK_SECTOR_WEIGHTS` and `get_sector_weights()` from `ic3_real.py`
   - Import or replicate size factor mapping from `loss_projection.py`
   - Compute industry exposure score from sector weights
   - Compute size factor from employee_range
   - Return structured breakdown dict
2. Create `RiskScoreResponse` schema in `backend/app/schemas/`
3. Add `GET /organizations/mine/risk` endpoint in `organizations.py`
4. Write unit tests

**Phase 2 — Frontend**
5. Add API client function in `frontend/src/api/`
6. Display risk score breakdown in dashboard (SmBAdvisorTab or new component)

### Verdict

~40% complete. The foundational data (sector weights, org model, enums) is solid, but the core deliverable (the scoring function + endpoint) hasn't been built yet. There's partial work on the `Risk-Scoring-and-fix-dashboard` branch that should be reviewed before starting fresh.

---

## Priority & Dependencies

| Priority | Ticket | Effort | Blocker? |
|---|---|---|---|
| 1 | SCRUM-46 | ~15 min | No — standalone fix |
| 2 | SCRUM-42 | ~30 min | No — decide on `/signup` route |
| 3 | SCRUM-52 | ~3-4 hrs | No — but check `Risk-Scoring-and-fix-dashboard` branch first |

**Recommended order:** SCRUM-46 first (trivial), then SCRUM-42 (quick decision + small change), then SCRUM-52 (largest remaining work).

---

## Key Files Reference

```
frontend/src/App.tsx                          # Route config
frontend/src/pages/LoginPage.tsx              # Login/signup page
frontend/src/components/ProtectedRoute.tsx    # Auth guard
frontend/src/components/dashboard/DashboardHeader.tsx  # Header auth UI
frontend/src/context/AuthContext.tsx           # Firebase auth state
frontend/src/api/fetchWithAuth.ts             # Authenticated fetch
frontend/tsconfig.json                        # TS config (line 28 exclusion)
frontend/src/pages/Dashboard.tsx              # Re-export + dead code
backend/app/services/risk_scoring.py          # Risk scoring functions
backend/app/ingestors/ic3_real.py             # ATTACK_SECTOR_WEIGHTS
backend/app/services/loss_projection.py       # Size factor mapping
backend/app/api/routes/v1/organizations.py    # Org endpoints
backend/app/db/organization.py                # Org model
backend/app/db/enums.py                       # EmployeeRange, IndustryLabel
.github/workflows/ci.yml                      # CI pipeline
```
