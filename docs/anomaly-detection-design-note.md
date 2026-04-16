# Anomaly Detection Design Note

**Project:** Hacker Tracker — Cyber Threat Intelligence & Anomaly Detection Platform
**Date:** 2026-04-15
**Status:** Design note / backlog recommendation

---

## 1. Definition of Anomaly Detection in Hacker Tracker

An anomaly in Hacker Tracker is a **statistically unusual observation** within one of the platform's four data domains that signals elevated risk to an organization or sector:

| Domain | Anomaly means |
|---|---|
| **IC3 / Cybercrime** | A state's complaint volume or financial loss is an outlier within its sector and year peer group, or a sector's totals spike sharply between years |
| **NVD / KEV** | A vendor's rate of published CVEs or confirmed-exploited vulnerabilities is unusual relative to peers or its own historical rate |
| **Org-specific** | A registered org's vendor stack has disproportionate KEV exposure relative to the global org population |
| **Economic** | Regional economic indicators (BEA) shift in ways that correlate with elevated SMB cyber risk |

Anomalies are **signals, not verdicts.** They surface data points that warrant manual review, not automated enforcement.

---

## 2. Current Capabilities

All three implemented methods live in [`backend/app/services/anomaly_detection.py`](../backend/app/services/anomaly_detection.py) and are exposed via [`backend/app/api/routes/v1/anomalies.py`](../backend/app/api/routes/v1/anomalies.py).

### 2.1 IC3 Cross-Sectional Z-Scores (`GET /anomalies/ic3`)

**What it does:** For each `(sector, year)` group, computes the population mean and standard deviation of `complaint_count` and `loss_amount` across all states. States whose z-score exceeds the configurable threshold (default `2.0`, range `0.5–5.0`) are flagged.

**Statistical approach:** Population z-score — `(x - μ) / σ` — computed entirely in SQL using `avg()` and `stddev_pop()`. A `nullif(std, 0)` guard prevents division by zero when all states in a group have the same value; those rows get z-score `0` via `coalesce`.

**Data requirements:** `IC3Incident` table — columns `sector`, `state`, `year`, `complaint_count`, `loss_amount`.

**Output fields per anomaly:** `sector`, `state`, `year`, `complaint_count`, `loss_amount`, `z_score_complaints`, `z_score_loss`, `anomaly_type` (`complaints | loss | both`).

**Limitations:**
- Dataset is ~75 rows (5 states × 5 sectors × 3 years). With only ~5 states per group, population stddev is computed over very few samples, making z-scores sensitive to a single outlier.
- No temporal component — each `(sector, year)` group is treated independently; longitudinal patterns are not captured here (see method 2.2).
- State selection is fixed to the IC3 source data; national-level comparison is not available.

### 2.2 Year-over-Year Trend Flagging (`GET /anomalies/trends`)

**What it does:** Aggregates IC3 totals per `(sector, year)` across all states, then computes YoY percentage change in `complaint_count` and `loss_amount`. Sectors where either metric changes by more than the configurable threshold (default `0.5 = 50%`, range `0.1–10.0`) are flagged.

**Statistical approach:** Simple percentage change — `(current - previous) / previous`. Aggregation is done in SQL; YoY comparison is computed in Python (dataset after aggregation is tiny: ~15 rows).

**Data requirements:** Same `IC3Incident` table as method 2.1.

**Output fields per entry:** `sector`, `year`, `complaint_count`, `loss_amount`, `prev_complaint_count`, `prev_loss_amount`, `yoy_change_complaints`, `yoy_change_loss`, `flagged`.

**Limitations:**
- No baseline normalization — a 50% jump from a very small base (e.g., 2 complaints → 3) triggers the same flag as a 50% jump from thousands.
- Only two consecutive years are compared at a time; there is no rolling window or multi-year trend line.
- Data covers a short time range (~3 years), limiting statistical significance of trend signals.

### 2.3 Vendor KEV Exposure Anomalies (`GET /anomalies/vendors`)

**What it does:** For an org's registered vendors, counts how many KEV entries match each vendor name. Z-scores each vendor's match count against the global distribution of all `(org, vendor)` match counts. Vendors exceeding the threshold (default `2.0`) are flagged as high-exposure outliers.

**Statistical approach:** Global population z-score computed in Python after a single SQL aggregation (`COUNT(KEV.id)` via left outer join on lowercased vendor name).

**Data requirements:** `OrgVendor` table (org vendor registrations) and `KEV` table (CISA known exploited vulnerabilities). Vendor name matching is case-insensitive exact match.

**Output fields:** Per-vendor `kev_match_count`, `global_avg_matches`, `z_score`, `anomaly` flag; plus org-level `org_total_matches` and `global_avg_total`.

**Limitations:**
- Vendor name matching is a lowercased exact string match — "Microsoft" and "Microsoft Corporation" are treated as different vendors. No fuzzy or normalized matching.
- The global baseline includes all orgs, including those with very few vendors. Baseline quality improves as more orgs register vendors.
- No temporal component — KEV matches are a snapshot; historical exposure trend is not tracked.
- Org-scoped: requires `get_current_org` dependency, so unauthenticated or org-less users cannot access this endpoint.

---

## 3. Gap Analysis

### 3.1 Temporal anomalies within NVD

**Gap:** No detection of CVE publication rate spikes by vendor or product over time.

A vendor that suddenly accounts for a much higher share of new CVEs in a rolling window (e.g., 30-day or 90-day) is a meaningful threat signal — but the platform currently treats NVD data as a static snapshot. There is no rolling baseline, no publication-rate time series, and no vendor-level spike detection.

**Data available:** `NVDVulnerability` table includes `published_date` and `vendor`/`product` fields (or equivalent). The data is already ingested.

### 3.2 Cross-source correlation

**Gap:** No signal fusion across IC3, KEV, and NVD.

A sector spike in IC3 complaints coinciding with a spike in KEV entries for vendors common in that sector is a much stronger signal than either alone. Currently, each data source is analyzed in isolation. There is no mechanism to correlate "Finance sector IC3 spike in 2023" with "Banking software vendors with new KEV entries in 2023."

### 3.3 Org-specific behavioral baselines

**Gap:** No tracking of changes to an org's own vendor stack or domain exposure over time.

The vendor anomaly method compares an org against the global org population — it does not detect when an org's own profile changes. If an org adds 10 new vendors that each have KEV matches, no drift alert is generated. Similarly, domain exposure changes (e.g., new subdomains, changed tech stack) are not baselined.

### 3.4 Economic indicator anomalies

**Gap:** BEA data is ingested but not used in any anomaly detection method.

Regional GDP and income indicators are available but serve only as contextual data on the Overview tab. No method detects when economic conditions in a region shift in ways that historically correlate with elevated SMB cyber risk.

---

## 4. Backlog Recommendations

### P1 — High value, data already available

**P1-A: NVD publication rate spike detection**
Detect when a vendor's share of new CVEs in a rolling 30/90-day window exceeds a z-score threshold versus its own historical rate or the global vendor average. Uses existing `NVDVulnerability` data. New endpoint: `GET /anomalies/nvd`. Adds a fourth sub-tab to `AnomaliesTab.tsx`.

**P1-B: Per-org anomaly summary card on Overview tab**
Surface the top 3 anomalies (highest absolute z-scores across IC3, trends, and vendor methods) as a summary card on the Overview tab. No new data fetching — aggregate existing anomaly API responses. Provides immediate value for users who don't navigate to the Anomalies tab.

### P2 — Medium value, requires design work

**P2-A: Cross-source correlation engine**
Produce a fused "elevated risk" signal when multiple independent anomaly sources align on the same sector/vendor/time window. Start with a rule-based approach (score = weighted sum of active anomalies per sector). New endpoint: `GET /anomalies/correlation`. Requires defining a shared taxonomy mapping IC3 sectors to KEV vendor categories.

**P2-B: Configurable alert thresholds per org**
Replace hardcoded defaults (`threshold=2.0`, `threshold_pct=0.5`) with per-org settings stored in the database. Adds an `AnomalyConfig` table and a settings UI panel. Enables orgs with different risk tolerances to tune sensitivity without changing code.

### P3 — Lower priority / future scale

**P3-A: Time-series baseline modeling**
Replace static z-scores with rolling window baselines (e.g., 12-month trailing mean/stddev per sector). Requires more historical data than currently available (~3 years of IC3). Revisit when data coverage expands.

**P3-B: ML-based outlier detection**
Consider Isolation Forest or DBSCAN for multi-dimensional anomaly detection once the dataset grows beyond current volumes. The current ~75 IC3 rows and ~15 aggregated trend rows are too few for ML methods to be more reliable than the statistical approaches already in place. Revisit at >500 rows per source.

---

## 5. Data Quality Constraints

| Source | Volume | Constraint |
|---|---|---|
| IC3 | ~75 rows (5 states × 5 sectors × ~3 years) | Very small sample per group. Z-scores computed over 5 observations per `(sector, year)` cell. Single outlier states heavily influence mean/stddev. Statistical significance is limited. |
| KEV | ~1,000+ entries | Vendor name strings are inconsistently formatted across entries. Exact-match joins miss vendor aliases and product-name variants. |
| NVD | Large (tens of thousands) | Not yet used for anomaly detection. Time-series analysis is feasible once a publication-rate aggregation query is written. |
| BEA / Economic | State-level annual summaries | Too coarse for meaningful anomaly detection without a more granular time series. Useful as contextual enrichment only at current granularity. |
| Org vendors | Depends on org registrations | Global baseline quality is low when few orgs have registered vendors. Vendor anomaly scores become more meaningful as the org count grows. |

---

## 6. Architectural Recommendations

### Current approach — keep as-is for current scale

All three methods use SQL aggregations (`avg`, `stddev_pop`, `sum`, `count`) computed at query time. No pre-computed state, no scheduled jobs, no external dependencies. This is appropriate for current data volumes and eliminates a class of data consistency bugs.

### If alert/notification features are planned — add an anomaly registry table

If the platform adds scheduled anomaly scans, user-visible alerts, or alert history, introduce a lightweight `anomaly_events` table:

```sql
CREATE TABLE anomaly_events (
    id          SERIAL PRIMARY KEY,
    source      TEXT NOT NULL,          -- 'ic3' | 'trends' | 'vendors' | 'nvd'
    entity_key  TEXT NOT NULL,          -- e.g. 'Finance:CA:2023' or 'org:42:vendor:Cisco'
    z_score     NUMERIC,
    flagged_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    threshold   NUMERIC NOT NULL,
    org_id      INTEGER REFERENCES organizations(id)  -- NULL for global anomalies
);
```

This avoids recomputing anomalies on every page load, enables historical comparisons ("was this flagged last week too?"), and unblocks notification workflows.

### Do not add ML dependencies at this stage

Adding `scikit-learn`, `numpy`, or `pandas` to the backend introduces significant deployment complexity (Docker image size, dependency conflicts, inference latency) for marginal gain over SQL z-scores given current data volumes. Revisit only if dataset size or detection accuracy requirements change substantially.
