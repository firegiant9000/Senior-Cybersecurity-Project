# Implementation Plan — SCRUM-24, 32, 37, 49

**Date:** 2026-04-10
**Author:** Arlo (via Claude)
**Scope:** Dashboard refactor, responsiveness improvements, production CORS/HTTPS hardening

---

## Execution Order

These issues have dependencies. Ship them in this order to minimize merge conflicts:

```
Phase 1: SCRUM-49  (CORS/HTTPS — backend, no frontend conflicts)
Phase 2: SCRUM-37  (Dashboard modularization — structural changes)
     └─ Close SCRUM-24 as duplicate
Phase 3: SCRUM-32  (Responsiveness — applies to the new modular files from Phase 2)
```

---

## Phase 1 — SCRUM-49: Production CORS & HTTPS Hardening

**Branch:** `feature/scrum-49-cors-https`
**Assignee:** PN
**Risk:** Medium — production config change, needs Render env var verification

### 1.1 Add CORS validation guard in config.py

**File:** `backend/app/core/config.py`

Add a Pydantic `model_validator` that rejects localhost origins when `APP_ENV` is not `development` or `testing`. Mirrors the existing SECRET_KEY guard pattern in `main.py:145-156`.

```python
from pydantic import model_validator

class Settings(BaseSettings):
    # ... existing fields ...

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        if self.APP_ENV not in ("development", "testing"):
            localhost_origins = [
                o for o in self.CORS_ORIGINS if "localhost" in o
            ]
            if localhost_origins:
                raise ValueError(
                    f"CORS_ORIGINS contains localhost entries {localhost_origins} "
                    f"but APP_ENV={self.APP_ENV!r}. "
                    "Set CORS_ORIGINS to production domains only."
                )
        return self
```

**Why model_validator instead of field_validator:** It needs access to both `APP_ENV` and `CORS_ORIGINS` simultaneously.

### 1.2 Set production defaults in config.py

Change the `CORS_ORIGINS` default so it's safe if the env var is missing:

```python
CORS_ORIGINS: list[str] = []  # must be set explicitly per environment
FRONTEND_URL: str = ""         # must be set explicitly per environment
```

Empty defaults mean production fails fast (no requests allowed) rather than silently accepting localhost.

### 1.3 Restrict CORS methods/headers in production

**File:** `backend/app/main.py` (around line 173)

```python
if settings.APP_ENV in ("development", "testing"):
    allowed_methods = ["*"]
    allowed_headers = ["*"]
else:
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    allowed_headers = ["Authorization", "Content-Type", "X-Requested-With"]

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
    expose_headers=["Retry-After"],
)
```

### 1.4 Update .env files

**`.env.example`** — add production example:
```
# Development
CORS_ORIGINS=["http://localhost:5173"]
# Production example:
# CORS_ORIGINS=["https://hacker-tracker-75f91.web.app"]
```

**`frontend/.env.production`** (new file):
```
VITE_API_BASE_URL=https://hacker-tracker-backend.onrender.com
```

Vite automatically loads `.env.production` when running `npm run build`.

### 1.5 Update render.yaml documentation

Add a comment block near the CORS_ORIGINS entry:

```yaml
- key: CORS_ORIGINS
  sync: false
  # REQUIRED: JSON array of allowed origins. Example:
  # ["https://hacker-tracker-75f91.web.app"]
  # App will refuse to start if this contains localhost in production.
```

### 1.6 Handle preview deploy origins

The PR preview deploy feature (commit `9d1ee3d`) creates dynamic Firebase preview URLs. Two options:

- **Option A (recommended):** Add the preview channel pattern to Render env: `["https://hacker-tracker-75f91.web.app", "https://hacker-tracker-75f91--*-*.web.app"]` — but CORSMiddleware doesn't support globs.
- **Option B (practical):** Add a `CORS_ORIGINS_PATTERN` field that accepts a regex, and implement a custom CORS origin check. Example:

```python
CORS_ORIGINS_PATTERN: str = ""  # regex, e.g. r"https://hacker-tracker-75f91--[\w-]+\.web\.app"
```

Then in `main.py`, if `CORS_ORIGINS_PATTERN` is set, subclass or configure the middleware to check origins against the pattern. This keeps preview deploys working without adding every preview URL manually.

**Simpler alternative:** Skip pattern matching and just add preview URLs to the env var as needed. Preview deploys are short-lived and dev-facing, so this is acceptable.

### 1.7 Verification

- [ ] `make backend-test` passes
- [ ] Local dev still works with `make up` (APP_ENV=development, localhost origins)
- [ ] Add a unit test: `APP_ENV=production` + localhost origin raises `ValueError`
- [ ] Confirm Render dashboard has `CORS_ORIGINS` set to `["https://hacker-tracker-75f91.web.app"]`
- [ ] Confirm frontend prod build uses the correct API URL via `.env.production`
- [ ] Hit the deployed backend from a non-allowed origin and verify the request is rejected

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Empty default breaks existing Render deploy if env var not set | Backend won't accept any requests | Verify Render env vars are set BEFORE merging; add startup log that prints allowed origins |
| Preview deploys blocked by CORS | PR previews can't hit backend | Use Option B pattern matching, or manually add preview URLs |
| Restricting allow_headers breaks a frontend request | Specific API call fails in prod | Test all frontend API calls against restricted headers locally by setting APP_ENV=production |

---

## Phase 2 — SCRUM-37: Dashboard Modularization

**Branch:** `feature/scrum-37-dashboard-refactor`
**Assignee:** CK
**Risk:** Low-Medium — structural refactor, no behavior change
**Note:** Close SCRUM-24 as duplicate of SCRUM-37 (identical title and assignee)

### 2.1 Create component subdirectories

```
frontend/src/components/
├── dashboard/          # NEW — overview-specific components
│   ├── OverviewTab.tsx
│   ├── OverviewTab.css
│   ├── DashboardHeader.tsx
│   ├── DashboardHeader.css
│   ├── DashboardToolbar.tsx
│   └── TabBar.tsx
├── tabs/               # NEW — move existing tab components here
│   ├── AlertsFeedTab.tsx
│   ├── CisaKevTable.tsx
│   ├── EconomicsTable.tsx
│   ├── IC3Table.tsx
│   ├── NvdTable.tsx
│   ├── PipelineHealthTab.tsx
│   ├── RiskScoringTable.tsx
│   ├── SmBAdvisorTab.tsx
│   ├── ThreatIntelTab.tsx
│   ├── TrendsTab.tsx
│   ├── VendorAlertsTab.tsx
│   └── VictimProfileTab.tsx
├── charts/             # NEW — move chart components here
│   ├── CyberSecurityMap.tsx
│   ├── IncidentManagementChart.tsx
│   ├── MalwareBarChart.tsx
│   ├── SectorAttackHeatmap.tsx
│   ├── SeverityDistributionChart.tsx
│   ├── CyberRisksTreemap.tsx
│   └── CyberRisksTiles.tsx
└── shared/             # NEW — move reusable UI components here
    ├── StatCard.tsx
    ├── SeverityBadge.tsx
    ├── WidgetErrorBoundary.tsx
    ├── WidgetSkeleton.tsx
    ├── ComplianceStatusBars.tsx
    ├── DataFreshness.tsx
    └── ProgressGauges.tsx
```

### 2.2 Extract OverviewTab from Dashboard.tsx

**Current state:** `Dashboard.tsx` (356 lines) renders the entire Overview tab inline, including the widget grid, toolbar, executive summary, and stat cards.

**Target:** `Dashboard.tsx` becomes a thin shell (~80 lines):
- Header (logo, user info, dark mode toggle, logout)
- Tab bar
- `<Suspense>` wrapper that renders the active tab component

The Overview tab content moves to `components/dashboard/OverviewTab.tsx`.

### 2.3 Extract DashboardHeader

Pull lines handling the header (title, dark mode toggle, user email, settings/logout buttons) into `DashboardHeader.tsx`. Props: `user`, `darkMode`, `onToggleDarkMode`, `onLogout`.

### 2.4 Extract TabBar

Pull the tab button rendering and `activeTab` state management into `TabBar.tsx`. Props: `activeTab`, `onTabChange`, `tabs` (array of `{id, label}`).

### 2.5 Split Dashboard.css

Break the 1,982-line file into scoped CSS files:

| New File | Lines (approx) | Content |
|----------|----------------|---------|
| `DashboardHeader.css` | ~80 | Header, user info, dark mode toggle styles |
| `TabBar.css` | ~60 | Tab container, tab buttons, active states |
| `OverviewTab.css` | ~400 | Dashboard grid, widget cards, stat cards, toolbar |
| `tables.css` | ~200 | Shared table styles (`.tab-table`, `.table-scroll-wrapper`, sticky headers) |
| `Dashboard.css` (remaining) | ~300 | Root variables, dark mode tokens, page-level layout, shared card base |
| Component-specific CSS | varies | Move component-specific rules into co-located files |

**Key rule:** Every extracted CSS file must import or inherit the `:root` and `[data-theme="dark"]` variables. Keep those in `Dashboard.css` (the root file) and ensure it's imported first.

### 2.6 Verification

- [ ] `npm run build` succeeds with no errors
- [ ] `npm run lint` passes
- [ ] All existing functionality works identically (visual regression check)
- [ ] Dark mode toggle still works on all extracted components
- [ ] Lazy loading still works for tab components (check network tab in devtools)
- [ ] No duplicate CSS rules across split files

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CSS cascade breaks after split | Styles missing or incorrect in some components | Keep `:root` variables in a single file imported at the top of the app; test dark mode on every tab |
| Import path changes break lazy loading | Tab components fail to load | Update all `React.lazy(() => import(...))` paths in Dashboard.tsx; verify with slow 3G throttling in devtools |
| Large diff causes merge conflicts with SCRUM-32 | Time lost resolving conflicts | Ship SCRUM-37 first, then rebase SCRUM-32 onto it |
| Moving 30 files changes git blame history | Harder to trace original authors | Use `git mv` for moves so git tracks the rename; add a note in the PR description |

---

## Phase 3 — SCRUM-32: Dashboard Responsiveness

**Branch:** `feature/scrum-32-responsive-dashboard`
**Assignee:** PN
**Risk:** Low — CSS/UI changes, no logic changes
**Depends on:** Phase 2 (applies changes to the new modular file structure)

### 3.1 Fix tab navigation for mobile

**File:** `TabBar.css` (after Phase 2 extraction) or `Dashboard.css` if Phase 2 hasn't shipped

**Current problem:** 14 tabs with `nowrap` overflow horizontally with no visible scroll indicator.

**Solution:** Add a tab overflow menu for screens under 768px:

```tsx
// TabBar.tsx — add a "More" dropdown for overflow tabs
// On mobile: show first 4 tabs + "More ▾" button
// Dropdown shows remaining tabs
```

Implementation:
- Track container width with a `ResizeObserver` or a simple `@media` query
- Below 768px: render a `<select>` dropdown or a "More" button with a popover
- Above 768px: keep current horizontal scroll with added gradient fade indicators on edges

### 3.2 Add table responsive card view

**Files:** All table components in `components/tabs/`

**Current problem:** Tables force horizontal scroll on mobile, which is hard to use.

**Solution:** Add a shared `ResponsiveTable` wrapper component:

```tsx
// components/shared/ResponsiveTable.tsx
// - Above 768px: render standard <table> with .table-scroll-wrapper
// - Below 768px: render each row as a stacked card
```

Apply to: `CisaKevTable`, `EconomicsTable`, `IC3Table`, `NvdTable`, `RiskScoringTable`

**Simpler alternative:** If card view is too much scope, just improve the existing scroll UX:
- Add horizontal scroll shadow/fade indicators
- Increase touch target size on sortable headers (min 44px)
- Add a "scroll to see more" hint on first render

### 3.3 Fix heatmap responsiveness

**File:** `components/charts/SectorAttackHeatmap.tsx` + its CSS

**Current problem:** `min-width: 600px` forces scroll on small screens.

**Solution:**
- Remove `min-width: 600px`
- Add horizontal snap-scroll with CSS `scroll-snap-type: x mandatory`
- Truncate long sector/attack labels on small screens with `text-overflow: ellipsis`
- Reduce cell padding at the 768px breakpoint

### 3.4 Fix chart responsiveness

**Files:** All chart components in `components/charts/`

- Replace hardcoded `height: 300` in `CisaKevTable.tsx` PieChart wrapper with `aspect-ratio: 1` or a percentage-based height
- Ensure all `<ResponsiveContainer>` wrappers have a parent with defined dimensions (not just `height: 100%` on an unsized parent)
- Add `aspect-ratio: 16/9` to chart containers as a CSS fallback

### 3.5 Fix VendorAlertsTab scroll wrapper

**File:** `components/tabs/VendorAlertsTab.tsx`

Replace inline `style={{ width: '100%' }}` with the `.table-scroll-wrapper` class used by all other tables.

### 3.6 Standardize mobile spacing

**Files:** All component CSS files

Audit and standardize mobile breakpoint values:
- Padding: 12px (cards), 8px (table cells)
- Font sizes: 14px (body), 12px (table cells), 16px (headings)
- Gap: 12px (grid gap at mobile)

### 3.7 Verification

- [ ] Test on Chrome DevTools device emulator: iPhone SE (375px), iPad (768px), laptop (1024px), desktop (1440px)
- [ ] Tab navigation works on all breakpoints — no unreachable tabs
- [ ] All tables are usable on mobile (either card view or improved scroll)
- [ ] Heatmap is readable on iPad without horizontal scroll
- [ ] Charts resize correctly when rotating device (portrait ↔ landscape)
- [ ] Dark mode still works at all breakpoints
- [ ] `npm run build` and `npm run lint` pass

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tab dropdown breaks keyboard navigation / a11y | Accessibility regression | Use `<select>` or proper `role="menu"` with arrow key support |
| Card view for tables loses column alignment context | Users can't compare rows easily | Keep standard table above 768px; only switch to cards on mobile |
| Heatmap becomes unreadable without min-width | Data too compressed | Test with real data; add a minimum cell size and let container scroll if needed |
| Spacing standardization causes visual regressions | Subtle layout shifts everywhere | Change one component at a time; screenshot compare before/after |

---

## Cross-Phase Dependency Map

```
SCRUM-49 (Phase 1)          SCRUM-37 (Phase 2)          SCRUM-32 (Phase 3)
─────────────────           ──────────────────          ──────────────────
config.py guard      ──┐
main.py CORS restrict   │    Dashboard.tsx shell
.env.production         │    OverviewTab extraction
render.yaml docs        │    CSS split ──────────────── Responsive fixes
                        │    File reorganization ─────── Apply to new paths
                        │    TabBar extraction ───────── Tab mobile menu
                        │
No frontend conflicts ──┘
```

---

## Consolidated Checklist

### Before Starting
- [ ] Confirm with CK: close SCRUM-24 as duplicate of SCRUM-37
- [ ] Verify Render dashboard has `CORS_ORIGINS` env var set to production domain
- [ ] Agree on tab mobile UX approach (dropdown vs. hamburger vs. scroll improvements)

### Phase 1 Deliverables
- [ ] CORS localhost guard in `config.py`
- [ ] Empty CORS defaults (fail-fast)
- [ ] Production-conditional `allow_methods` / `allow_headers`
- [ ] `frontend/.env.production` with prod API URL
- [ ] Updated `.env.example` with production example
- [ ] Unit test for CORS validation
- [ ] Render env var verified

### Phase 2 Deliverables
- [ ] `components/dashboard/`, `components/tabs/`, `components/charts/`, `components/shared/` directories created
- [ ] `OverviewTab.tsx` extracted
- [ ] `DashboardHeader.tsx` extracted
- [ ] `TabBar.tsx` extracted
- [ ] `Dashboard.css` split into 5+ scoped files
- [ ] `Dashboard.tsx` reduced to ~80 lines
- [ ] All imports updated, lazy loading verified

### Phase 3 Deliverables
- [ ] Tab mobile menu/dropdown implemented
- [ ] Table scroll UX improved (shadows, touch targets) or card view added
- [ ] Heatmap min-width removed, snap-scroll added
- [ ] Chart heights use aspect-ratio instead of fixed px
- [ ] VendorAlertsTab scroll wrapper fixed
- [ ] Mobile spacing standardized
- [ ] Tested on 4 breakpoints (375px, 768px, 1024px, 1440px)
