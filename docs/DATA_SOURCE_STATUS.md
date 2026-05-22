# Data Source Status

Authoritative list of every dashboard dataset and its current backing. The
frontend renders a `real | static | mocked | pending` badge on each widget
that pulls from this registry. The single source of truth is
[backend/app/services/data_status.py](../backend/app/services/data_status.py)
(exposed at `GET /api/v1/data-status`). This document mirrors that registry
for human review and audit purposes.

> **Update rule:** edit the Python registry first; this doc reflects it.
> If they drift, the registry wins — file a PR to re-sync the doc.

---

## Status meanings

| Status    | Meaning                                                                  |
|-----------|--------------------------------------------------------------------------|
| `real`    | Live data refreshed from the upstream source on a scheduled cadence.    |
| `static`  | Curated snapshot. Updates only when the source itself releases new data.|
| `mocked`  | Placeholder values. Not real data. Should not be used for decisions.    |
| `pending` | Feature is wired up but no data has been ingested yet.                  |

---

## Registry

| Dataset key                  | Widget / surface                          | Status   | Source                                                                |
|------------------------------|-------------------------------------------|----------|-----------------------------------------------------------------------|
| `nvd_cves`                   | NVD CVE catalog, totals, severity bars   | real     | NIST National Vulnerability Database (scheduled ingest)              |
| `kev`                        | KEV count, CVEs Exploited card           | real     | CISA KEV catalog (scheduled ingest)                                  |
| `epss`                       | Exploitability column in NVD table       | real     | FIRST.org EPSS API — daily scheduled ingest                          |
| `ic3_incidents`              | IC3 incident list + most stat cards      | static   | FBI IC3 2023 annual report (static summary)                          |
| `ic3_geographic`             | Cyber Crime Map, States with Incidents   | static   | FBI IC3 2023 annual report (static summary)                          |
| `ic3_sector_attack_matrix`   | Sector × Attack heatmap, Incident Mgmt   | static   | FBI IC3 2023 annual report (static summary)                          |
| `ic3_temporal_trends`        | YoY trend lines, Escalating Sectors      | static   | FBI IC3 annual reports (multi-year static)                           |
| `bea_economics`              | Economic indicators tab                  | real     | U.S. Bureau of Economic Analysis API                                 |
| `executive_summary`          | Executive Summary card                   | real     | Derived from org profile + NVD/KEV/IC3 aggregates                    |
| `risk_score`                 | Avg CVE Risk Score, CVE Risk Distribution| real     | Derived from CVSS + KEV signals                                      |
| `vendor_alerts`              | Vendor Alerts card                       | real     | KEV matches against the org's declared vendor stack                  |
| `loss_projection`            | Projected Annual Loss card               | static   | Statistical model over IC3 sector benchmarks                         |
| `ai_summary`                 | AI Summary tab                           | real     | LLM-generated summary over current dashboard signals                 |
| `domain_checks`              | Domain reputation tab                    | pending  | HIBP / Shodan / OTX — Month 1 Phase E (#110)                         |
| `anomalies_ic3`              | State Threat Anomalies card              | static   | Statistical z-score over IC3 static dataset                          |
| `anomalies_vendors`          | Vendor anomaly tab                       | real     | Derived from live KEV / NVD signals                                  |
| `assets_inventory`           | Assets tab, Inventory Health card        | real     | User-uploaded CSV (Phase C) + M365 sync (Phase E, behind flag)       |
| `asset_software`             | Per-asset software list, drill-down      | real     | Derived from uploaded inventory                                      |
| `scan_runs`                  | Upload history / "last upload" badge     | real     | One row per CSV upload / M365 sync                                   |
| `asset_kev_matches`          | Asset → CVE drill-down, KEV badges       | real     | Literal vendor+product match — preliminary until Month 3 CPE matcher |
| `vendor_aliases`             | Matcher dictionary (Month 3 input)       | static   | Hand-curated alias → canonical map (Phase A5 seed)                   |

---

## Demo mode (per-organisation)

`ENABLE_DEMO_MODE` (a global config flag) was removed in Month 1 Phase C.
Demo behaviour is now per-organisation, driven by the
`organizations.is_demo` column. When that flag is `true`, repositories serve
data from curated fixtures instead of the live database.

Unauthenticated routes (e.g. `GET /api/v1/public/stats`) have no caller-
supplied org context. Any future public route that needs fixture-backed
data must resolve to the canonical **Public Demo** organisation seeded by
[`backend/scripts/seed_demo_org.py`](../backend/scripts/seed_demo_org.py)
— do not introduce a parallel "global demo" switch.

## Data lifecycle (Month 1 Phase C2)

| Operation                                         | Endpoint                                    | Audit-log action       |
|---------------------------------------------------|---------------------------------------------|------------------------|
| Hard-delete org + every tenant-scoped row         | `DELETE /api/v1/organizations/{id}`         | `organization.delete`  |
| Stream full JSON export of the org's rows         | `GET /api/v1/organizations/{id}/export`     | `organization.export`  |
| Manual retention sweep (no-op until Month 4)      | `POST /api/v1/organizations/{id}/retention/run` | (none, dry-run)    |

Both write a row to `audit_log` capturing `actor_user_id`, `org_id`, and
per-table counts. The retention policy is documented in
[`backend/app/services/retention.py`](../backend/app/services/retention.py).

## Audit checklist (before merging changes to the dashboard)

1. Did you add or rename a widget? Add / update its entry in
   `backend/app/services/data_status.py` first.
2. Did you change a dataset's backing (e.g. static → real)? Update the
   `status` field — the frontend badge will pick it up automatically.
3. Cross-check the running dashboard: every widget must show a badge.
   Open `/?tab=overview` on staging — no unlabeled widgets.
4. If a widget pulls from multiple datasets, pick the *least confident*
   status (e.g. real + static → static) so we don't overpromise.
