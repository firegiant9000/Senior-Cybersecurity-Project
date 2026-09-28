# Implementation Guide — Remaining Open Issues

## Overview

This guide covers 5 open GitHub issues: #31, #8, #6, #33, #32. Each section details what needs to be done, potential issues that may arise, and how to remedy them.

---

## Issue #31 — Improve Dashboard UI Layout & Responsiveness

### What to implement
1. Make tabs horizontally scrollable on mobile instead of wrapping
2. Add `overflow-x: auto` table wrappers to NvdTable, CisaKevTable, EconomicsTable, RiskScoringTable
3. Add responsive breakpoints at 768px for table padding/font-size, filter controls, chart grid heights
4. Fix pagination dark mode (hardcoded `#0b1060` → `var(--accent)`)
5. Reduce tab content padding on mobile (30px → 16px)

### Files to modify
- `frontend/src/Dashboard.css` — bulk of responsive rules
- `frontend/src/components/NvdTable.tsx` — wrap `<table>` in scrollable div
- `frontend/src/components/CisaKevTable.tsx` — same + fix pie chart fixed height
- `frontend/src/components/EconomicsTable.tsx` — same
- `frontend/src/components/RiskScoringTable.tsx` — same

### Potential Issues & Remedies

**1. Horizontal tab scroll hiding active tab indicator**
- Problem: Changing `.tabs-container` from `flex-wrap: wrap` to `overflow-x: auto; flex-wrap: nowrap` means the active tab underline/border may scroll off-screen and the user won't know which tab is selected.
- Remedy: Add JavaScript to scroll the active tab into view on tab change:
  ```js
  const tabRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { tabRef.current?.scrollIntoView({ behavior: 'smooth', inline: 'center' }); }, [activeTab]);
  ```

**2. Recharts charts collapsing to 0 height when grid rows change to `auto`**
- Problem: Recharts `ResponsiveContainer` with `height="100%"` requires a parent with an explicit height. Setting `grid-template-rows: auto` removes the explicit height, causing charts to collapse.
- Remedy: Use `minmax(240px, auto)` instead of pure `auto`, or set `min-height: 240px` on chart card divs. This preserves a minimum while allowing growth.

**3. Table horizontal scroll conflicting with sticky headers**
- Problem: If tables use `position: sticky` on `<thead>`, wrapping in `overflow-x: auto` can break the sticky behavior in some browsers.
- Remedy: Apply `overflow-x: auto` to a wrapper div around the table, not on the table itself. Keep sticky headers inside the scroll container. Test on Chrome, Firefox, Safari.

**4. Dark mode CSS variable cascade issues**
- Problem: Replacing hardcoded colors with `var(--accent)` requires that the variable is defined in both light and dark theme scopes. If it's missing in one, buttons become invisible.
- Remedy: Verify both `:root` and `[data-theme="dark"]` define `--accent`. Add fallback: `background-color: var(--accent, #0b1060)`.

**5. Filter controls stacking may push table off-screen on mobile**
- Problem: Stacking filter groups vertically on mobile can create a tall filter area that pushes the actual data table below the fold.
- Remedy: Add a collapsible filter section: collapsed by default on mobile with a "Show Filters" toggle button. Or limit visible filters to search + one dropdown, with an "Advanced" expander.

---

## Issue #8 — Clean Up Dashboard (Filter & Search)

### What to implement
1. Add "Reset Filters" button to all 5 table components
2. Add date range filter to NvdTable (requires backend `/cves` endpoint update)
3. Add search + severity filter to RiskScoringTable
4. Add sortable column headers to EconomicsTable
5. Wire IC3 `search` param through backend route to repository
6. Standardize filter UI patterns across tables

### Files to modify
- `frontend/src/components/NvdTable.tsx` — date range inputs + reset button
- `frontend/src/components/CisaKevTable.tsx` — reset button
- `frontend/src/components/IC3Table.tsx` — reset button
- `frontend/src/components/EconomicsTable.tsx` — sortable headers + reset button
- `frontend/src/components/RiskScoringTable.tsx` — search + severity + reset
- `backend/app/api/routes/v1/nvd.py` — add `date_from`/`date_to` to `/cves`
- `backend/app/api/routes/v1/ic3.py` — wire `search` param through
- `backend/app/api/routes/v1/vulnerabilities.py` — add `search`/`severity` to `/risk-scored`

### Potential Issues & Remedies

**1. Adding `date_from`/`date_to` to NVD `/cves` breaks existing frontend calls**
- Problem: If the backend changes query behavior (e.g., defaults to a date range), existing calls without date params may return fewer results than expected.
- Remedy: Make `date_from` and `date_to` optional with `None` defaults. Only apply the SQL `WHERE` clause when they're provided. Existing calls remain unchanged.

**2. IC3 `search` param — SQL injection risk**
- Problem: Wiring a new `search` parameter through to SQL queries introduces injection risk if not properly parameterized.
- Remedy: The existing IC3 repository already uses SQLAlchemy's `ilike()` with parameterized queries. Follow the same pattern: `IC3Incident.attack_type.ilike(f"%{search}%")`. Never use f-strings in raw SQL.

**3. Reset Filters causing unnecessary API calls**
- Problem: If each filter state change triggers a separate API call, clicking "Reset" could fire multiple requests simultaneously (one per filter being cleared).
- Remedy: Batch state updates. Use a single `setFilters({})` call that resets all state at once, then trigger one API fetch. Or use `useRef` to debounce:
  ```js
  const resetFilters = () => {
    setSearch(''); setSeverity(''); setDateFrom(''); setDateTo('');
    setPage(1); // single re-render triggers one fetch
  };
  ```

**4. Sortable column headers conflicting with backend pagination**
- Problem: If the frontend sorts client-side but the backend paginates server-side, the user sees sorted results for the current page only, not the full dataset.
- Remedy: Column header clicks should update `sort_by` and `sort_order` query params sent to the backend, NOT sort client-side. Reset to page 1 on sort change.

**5. Filter UI inconsistency — checkboxes vs dropdowns**
- Problem: NvdTable uses checkboxes for severity (multi-select), CisaKevTable uses a dropdown (single-select). Standardizing to one pattern may change user behavior.
- Remedy: Standardize on dropdowns for single-select filters (severity, year, state) and keep search as a text input. If multi-select severity is needed, use a multi-select dropdown component rather than raw checkboxes. Document the pattern for future contributors.

**6. RiskScoringTable — backend doesn't support `search`/`severity` params**
- Problem: Adding frontend filters without backend support means the filters won't work.
- Remedy: Update `backend/app/api/routes/v1/vulnerabilities.py` `/risk-scored` endpoint to accept `search` (str, optional) and `severity` (str, optional). Apply filtering in the SQL query the same way `/exploited` does it.

---

## Issue #6 — Pipeline Health

### What to implement

**Backend:**
1. Create `IngestTrackingService` in `backend/app/services/ingest_tracking.py`
2. Add `/api/v1/ingest/runs` endpoint — paginated historical run list
3. Expand `/api/v1/ingest/freshness` response to include `error_message`
4. Re-instrument all 4 ingestors (nvd, cisa_kev, ic3, econ) to call tracking

**Frontend:**
5. Create `PipelineHealthTab.tsx` — run history table with status badges
6. Add "Pipeline Health" tab to Dashboard.tsx
7. Extend `frontend/src/api/ingest.ts` with new API functions

### Files to create
- `backend/app/services/ingest_tracking.py`
- `frontend/src/components/PipelineHealthTab.tsx`

### Files to modify
- `backend/app/api/routes/v1/ingest.py` — new endpoint + schema update
- `backend/app/schemas/ingest_run.py` — extend response schemas
- `backend/app/ingestors/cisa_kev.py` — add tracking calls
- `backend/app/ingestors/nvd.py` — add tracking calls
- `backend/app/ingestors/ic3_real.py` — add tracking calls
- `backend/app/ingestors/econ.py` — add tracking calls
- `frontend/src/Dashboard.tsx` — add tab button + lazy import
- `frontend/src/api/ingest.ts` — add fetchIngestRuns()

### Potential Issues & Remedies

**1. Ingestor instrumentation breaking existing ingestion pipelines**
- Problem: Adding tracking calls (start_ingest_run/finish_ingest_run) to ingestors introduces a new DB dependency. If the `ingest_runs` table doesn't exist or the tracking code throws, the actual data ingestion fails.
- Remedy: Wrap all tracking calls in try/except blocks. Tracking failures should log warnings but NEVER prevent data ingestion:
  ```python
  try:
      run = await tracking.start_run("nvd")
  except Exception:
      logger.warning("Failed to start ingest tracking", exc_info=True)
      run = None
  # ... do actual ingestion ...
  if run:
      try:
          await tracking.finish_run(run, status="success", records=count)
      except Exception:
          logger.warning("Failed to finish ingest tracking", exc_info=True)
  ```

**2. Historical instrumentation was lost/reverted — why?**
- Problem: Git history shows tracking was implemented in commits 7b05b79, 1b5e296, a9c86c6, 1fdf594 but these changes aren't on main. They may have been reverted due to bugs.
- Remedy: Before re-implementing, check `git log --all --oneline -- backend/app/services/ingest_tracking.py` and `git log --all --grep="revert" --oneline` to understand WHY it was removed. The original implementation may have had circular import issues or session management bugs. Design the new service to be dependency-free (pass session in, don't import it).

**3. `/api/v1/ingest/runs` returning huge result sets**
- Problem: Over time, ingest runs accumulate. Without pagination, this endpoint could return thousands of rows.
- Remedy: Add pagination from day one: `page`, `page_size` (default 20, max 100). Add optional `source` filter and `status` filter. Sort by `started_at DESC` by default.

**4. Adding a new tab breaks the existing tab layout**
- Problem: Dashboard already has 10 tabs. Adding an 11th makes the horizontal scroll even worse (compounds issue #31).
- Remedy: Implement #31's tab scroll fix FIRST, then add the Pipeline Health tab. Or place Pipeline Health under a "System" or "Admin" section rather than as a top-level tab.

**5. IngestRun `finished_at` is NULL for crashed/interrupted runs**
- Problem: If an ingestor crashes mid-run, `finished_at` stays NULL and `status` stays "running" forever, showing permanently stale data.
- Remedy: Add a staleness check in the freshness endpoint: if `status="running"` and `started_at` is more than 1 hour ago, return `status="stale"`. The frontend can display this as a warning badge.

**6. Concurrent ingest runs creating duplicate records**
- Problem: If two instances of the same ingestor run simultaneously (e.g., manual + scheduled), both create "running" records for the same source.
- Remedy: Add a check before starting: query for existing "running" records for the same source. If found, either skip or mark the old one as "interrupted" before starting a new one.

---

## Issue #33 — Unit Tests for Risk Scoring & Validation Schemas

### What to implement
1. Create `backend/tests/test_risk_scoring.py` — tests for `calculate_risk_score()` and `basic_vuln_risk_score()`
2. Create `backend/tests/test_validators.py` — tests for all 10 validator functions + 4 Pydantic schemas

### Files to create
- `backend/tests/test_risk_scoring.py`
- `backend/tests/test_validators.py`

### Potential Issues & Remedies

**1. `calculate_risk_score()` expects ORM model objects — how to mock?**
- Problem: The function signature is `calculate_risk_score(cve, kev, incidents, econ)` where each is an ORM model instance. Creating real ORM objects requires a database session.
- Remedy: Use `unittest.mock.MagicMock` or simple dataclasses/namedtuples. The function only accesses attributes like `cve.cvss_score`, `kev` (existence check), `incident.loss_amount`, `econ.smb_count`. Example:
  ```python
  from unittest.mock import MagicMock

  cve = MagicMock()
  cve.cvss_score = 9.0

  kev = MagicMock()  # just needs to be truthy

  incident = MagicMock()
  incident.loss_amount = 2_000_000

  econ = MagicMock()
  econ.smb_count = 60_000
  ```

**2. Tests import paths — running tests from wrong directory**
- Problem: `from app.services.risk_scoring import calculate_risk_score` fails if pytest is run from the repo root instead of `/backend`.
- Remedy: Always run tests from the `backend/` directory: `cd backend && python -m pytest tests/`. Or add `backend` to the Python path in conftest.py:
  ```python
  import sys, os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
  ```

**3. Pydantic schema validation behavior differs between v1 and v2**
- Problem: If the project uses Pydantic v2 (likely, given FastAPI 0.100+), validation behavior differs from v1. `validator` → `field_validator`, error types change.
- Remedy: Check `pip show pydantic` for the version. Use `model_validate()` instead of direct instantiation for testing. Catch `pydantic.ValidationError` and check `.errors()` for specific field failures:
  ```python
  from pydantic import ValidationError

  def test_invalid_cvss():
      with pytest.raises(ValidationError) as exc_info:
          NvdCveValidationSchema(cve_id="CVE-2021-44228", cvss_score=15.0, ...)
      assert "cvss_score" in str(exc_info.value)
  ```

**4. `normalize_*` functions silently return None — easy to miss bugs**
- Problem: The normalize variants (e.g., `normalize_cvss_score`) return `None` on invalid input instead of raising. Tests that assert `is None` may pass even if the function is broken in a different way.
- Remedy: Test both the valid AND invalid paths explicitly. For valid inputs, assert the exact return value. For invalid inputs, assert `is None` AND verify the validate variant raises:
  ```python
  def test_normalize_cvss_valid():
      assert normalize_cvss_score(7.5) == 7.5  # exact value

  def test_normalize_cvss_invalid():
      assert normalize_cvss_score(15.0) is None  # returns None
      with pytest.raises(ValueError):
          validate_cvss_score(15.0)  # raises
  ```

**5. Risk scoring boundary tests — floating point precision**
- Problem: `min(cvss_score * 10, 40)` with a score of 4.0 should give exactly 40. But floating point math can produce 39.99999999 or 40.00000001.
- Remedy: Use `pytest.approx()` for floating point comparisons:
  ```python
  assert calculate_risk_score(cve, None, [], None) == pytest.approx(40.0)
  ```

---

## Issue #32 — API Endpoint Tests for Auth, NVD, KEV, IC3 Analytics

### What to implement
1. Create `backend/tests/test_auth.py` — register, login, /me
2. Create `backend/tests/test_ic3_analytics.py` — all 6 IC3 analytics endpoints
3. Create `backend/tests/test_kev_endpoints.py` — severity-summary, risk-scored, stats
4. Create `backend/tests/test_ingest_freshness.py` — freshness endpoint

### Files to create
- `backend/tests/test_auth.py`
- `backend/tests/test_ic3_analytics.py`
- `backend/tests/test_kev_endpoints.py`
- `backend/tests/test_ingest_freshness.py`

### Files to modify
- `backend/tests/conftest.py` — add auth fixtures, potentially DB session override

### Potential Issues & Remedies

**1. CRITICAL: Tests require a running PostgreSQL database**
- Problem: The current test setup uses the REAL database via `get_session`. No mocking exists. Tests will fail with `ConnectionRefusedError` if PostgreSQL isn't running.
- Remedy (Option A — recommended for this project): Accept this as integration tests. Document that `docker-compose up postgres` must be running before tests. Add a pytest marker:
  ```python
  @pytest.mark.skipif(not DB_AVAILABLE, reason="PostgreSQL not running")
  ```
- Remedy (Option B — more robust): Override `get_session` in conftest.py with an in-memory SQLite async engine:
  ```python
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
  from sqlalchemy.orm import sessionmaker
  from app.db.base import Base
  from app.db.engine import get_session
  from app.main import app

  test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

  @pytest.fixture(autouse=True)
  async def setup_db():
      async with test_engine.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
      yield
      async with test_engine.begin() as conn:
          await conn.run_sync(Base.metadata.drop_all)

  @pytest.fixture
  async def client(setup_db):
      async def override_session():
          async with AsyncSession(test_engine) as s:
              yield s
      app.dependency_overrides[get_session] = override_session
      async with AsyncClient(app=app, base_url="http://test") as c:
          yield c
      app.dependency_overrides.clear()
  ```
  **Caveat:** SQLite doesn't support all PostgreSQL features (e.g., `ILIKE`, array types). Some queries may need adjustment.

**2. Auth tests — creating test users leaves data in the database**
- Problem: `POST /register` creates a real user. Running tests repeatedly causes 409 conflicts on duplicate emails.
- Remedy: Use unique emails per test run (e.g., `f"test_{uuid4()}@example.com"`). Or wrap each test in a transaction that rolls back:
  ```python
  @pytest.fixture
  async def auth_client(client):
      email = f"test_{uuid4().hex[:8]}@example.com"
      await client.post("/api/v1/auth/register", json={"email": email, "password": "TestPass123!"})
      resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "TestPass123!"})
      token = resp.json()["access_token"]
      client.headers["Authorization"] = f"Bearer {token}"
      return client
  ```

**3. IC3 analytics tests return empty results on empty database**
- Problem: Analytics endpoints aggregate data. On an empty DB, they return `{"items": [], "year": null}`. Tests can't verify meaningful computation.
- Remedy: Accept empty results as valid (test response structure, not content). Use status code checks:
  ```python
  async def test_attack_types(client):
      resp = await client.get("/api/v1/ic3/analytics/attack-types")
      assert resp.status_code in (200, 500)  # 500 = DB unavailable
      if resp.status_code == 200:
          data = resp.json()
          assert "items" in data
  ```
  This pattern is already used in `test_filters.py` — follow the established convention.

**4. KEV endpoints — demo mode vs SQL mode behavior differs**
- Problem: With `ENABLE_DEMO_MODE=True`, KEV endpoints read from `fixtures/exploited_vulns.json` and always return data. With `False`, they query PostgreSQL. Tests may pass in one mode but fail in the other.
- Remedy: Test in demo mode by default (ensures tests pass without DB). Add a separate test suite for SQL mode that requires the DB:
  ```python
  @pytest.fixture
  def demo_mode(monkeypatch):
      monkeypatch.setattr("app.core.config.settings.ENABLE_DEMO_MODE", True)
  ```

**5. JWT token expiration in tests**
- Problem: If tests run slowly or are paused in a debugger, JWT tokens expire (default is typically 30-60 minutes). Auth tests intermittently fail.
- Remedy: Set a long expiration for tests:
  ```python
  @pytest.fixture
  def long_token(monkeypatch):
      monkeypatch.setattr("app.core.config.settings.ACCESS_TOKEN_EXPIRE_MINUTES", 9999)
  ```

**6. Test ordering dependencies**
- Problem: If `test_register` creates a user that `test_login` depends on, test execution order matters. Pytest doesn't guarantee order.
- Remedy: Never depend on other tests' side effects. Each test should set up its own preconditions. Use fixtures, not test chaining.

**7. Rate limiting or middleware blocking test requests**
- Problem: If the app has rate limiting or CORS middleware, rapid test requests may be throttled or rejected.
- Remedy: Check `backend/app/main.py` for middleware. Disable rate limiting in test mode, or use a test-specific app instance.

---

## Implementation Order (Recommended)

Implement in this order to avoid compounding issues:

1. **#33 first** — Unit tests for risk scoring + validators (pure Python, no DB needed, no frontend changes)
2. **#32 second** — API endpoint tests (builds on test infrastructure, identifies broken endpoints)
3. **#31 third** — UI responsiveness (CSS-only changes, low risk, visually verifiable)
4. **#8 fourth** — Filter/search improvements (requires backend + frontend changes, builds on #31's responsive work)
5. **#6 last** — Pipeline Health (largest scope, new tab + new endpoints + ingestor changes)

This order minimizes dependencies: tests first (catch bugs early), then UI fixes, then new features.
