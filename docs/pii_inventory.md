# PII Inventory

First-pass inventory of personally identifying or sensitive data the platform handles, plus the scrubbing rules applied before any of it leaves the process (logs, Sentry, exports). This will be expanded in Month 1 Phase D (#109 trust docs) — this version exists to back the Phase B observability work.

## Categories of sensitive data

| Category | Where it lives | Notes |
|---|---|---|
| User email | `users.email`, Firebase ID-token claims, audit log actor field | Required for auth; never logged in plaintext. |
| User UID | Firebase `uid`, attached to `users` and `organization_members` | Opaque — safe to log as `user_id`. |
| Org name | `organizations.name` | Customer-supplied; treat as confidential. |
| Org domains | `org_domains.domain` | Treat as confidential — knowing a customer's domain reveals identity. |
| Asset hostnames | future `assets.hostname` | Confidential — internal naming often leaks org structure. |
| IP addresses | request logs, future asset records | Excluded from Sentry (`send_default_pii=False`). |
| Vendor / product names supplied by user | onboarding inputs, vendor watchlists | Confidential but low sensitivity. |
| API keys (NVD, HIBP, Shodan, OTX, Gemini, Firebase) | env vars only | Never persisted to DB; never logged. |
| Firebase Bearer tokens | `Authorization` request header | Scrubbed from Sentry and JSON logs. |

## Scrubbing rules — Sentry (`backend/app/core/observability.py`)

The `before_send` hook runs on every event before transmission. Both keys and string values are scrubbed.

**Redacted key substrings (case-insensitive):**
- `authorization`
- `cookie`
- `password`
- `secret`
- `token`
- `api_key`, `apikey`
- `email`
- `hostname`, `host_name`

**Redacted string patterns:**
- Email addresses matching `[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}` → `[redacted]`

Sentry is additionally configured with `send_default_pii=False`, which suppresses automatic capture of IP addresses, request bodies, and user identifiers.

## Scrubbing rules — frontend Sentry (`frontend/src/lib/observability.ts`)

Mirrors the backend list. Any event captured client-side passes through the same key/value redaction before transmission. `sendDefaultPii: false` is set.

## Structured logs (`backend/app/core/logging.py`)

JSON logs include the correlation context (`request_id`, `org_id`, `user_id`) but not the user's email or org name. Application code is expected to log identifiers (UIDs, integer IDs), not human-readable PII. If a future log call needs to include user-supplied content (e.g., uploaded filename), it must be redacted at the call site.

## Third-party processors

What leaves our infrastructure, where it goes, and why.

| Processor        | Data sent                                                          | Purpose                |
|------------------|--------------------------------------------------------------------|------------------------|
| Firebase Auth    | Email, password (TLS), Firebase UID                               | Authentication         |
| Sentry           | Scrubbed exceptions + `request_id` / `org_id` / `user_id` tags    | Error monitoring       |
| Render           | All persisted data (managed PostgreSQL + backend host)            | Hosting + DB           |
| Firebase Hosting | Static frontend assets only                                       | Frontend hosting       |
| OpenAI (planned) | Aggregated org signals — never individual user identifiers        | AI summary generation  |
| NVD / KEV / BEA  | Outbound only — public APIs, no PII transmitted                   | Threat-intel ingest    |

## Data lifecycle paths (Phase C / #108)

- **Export:** `GET /api/v1/organizations/{id}/export` (admin-only) streams a
  JSON dump of every row associated with the org. The export includes all
  fields catalogued above. The request is recorded in `audit_log` with the
  acting user's ID.
- **Delete:** `DELETE /api/v1/organizations/{id}` (admin-only) iterates every
  table that references the org and removes rows explicitly — we do not rely
  on FK cascade so future tables cannot silently leak data. The deletion is
  recorded in `audit_log` and the audit row itself ages out under the
  12-month retention policy planned for Month 4.

## Retention (planned — Month 4)

- `audit_log`: 12 months rolling.
- `scan_runs`: 12 most recent runs per asset (rolling window).
- `uploads`: deleted on org purge; otherwise retained until the org admin
  removes them.

## Companion docs

- [DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md) — what data backs each widget.
- [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md) — what the
  product actually does today.
- [privacy.md](privacy.md) — user-facing privacy promise.
