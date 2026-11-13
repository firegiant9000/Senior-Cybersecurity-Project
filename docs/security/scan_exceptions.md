# Scan exceptions

Findings from security scanners that are knowingly left unfixed. Every entry has an expiry, and CI fails when an entry is expired or its window is too long.

## Policy

- Upgrade first. An exception is only for a finding with no fixed version, or a fix that is a breaking major upgrade needing its own work.
- The maximum window is 90 days (`Expires` minus `Added`). Exactly 90 days is allowed.
- Renewing means a new `Added` date and a fresh justification. Extending `Expires` alone is not a renewal.
- An entry is valid through its `Expires` date and fails the day after.
- `pip-audit`, `trivy`, `semgrep` and `zap` entries are suppressed in CI from this list (`python .github/scripts/scan_exceptions.py ids <scanner>`).
- `npm-audit`, `govulncheck` and `codeql` entries are recorded here but suppressed by other means: npm `overrides`, or a CodeQL dismissal whose comment cites the entry ID.
- A false positive or an intentional pattern is not an exception: dismiss the alert with a comment that names the control and the test. Exceptions are for real findings left unfixed.
- Dates are `YYYY-MM-DD`. Scanner is one of `pip-audit`, `npm-audit`, `govulncheck`, `trivy`, `codeql`, `semgrep`, `alembic-check`, `zap` (the ID is the ZAP plugin id, for example `10038`).
- The `## Exceptions` section holds only the table (no code blocks, nothing after the table), and the checker rejects anything else.
- Do not put secrets or personal data in this file.

## Exceptions

| ID | Scanner | Package / location | Reason | Compensating control | Added | Expires |
| --- | --- | --- | --- | --- | --- | --- |
| 10055 | zap | /docs (backend Swagger UI page; script-src and style-src unsafe-inline) | FastAPI's Swagger UI page needs inline script and style. The alert occurs only on /docs. An exception matches the plugin id on every URL, so after the fix/s5-policy PR merges, drop /docs from the ZAP seeds and delete this row | /docs, /redoc and /openapi.json are disabled in production (fix/s5-policy, "disable OpenAPI docs in production"); API routes raise no medium alerts | 2026-11-12 | 2026-12-12 |
| 90003 | zap | /docs (backend Swagger UI page; assets loaded from a CDN without integrity attributes) | FastAPI's Swagger UI page loads its assets from a CDN. The alert occurs only on /docs. An exception matches the plugin id on every URL, so after the fix/s5-policy PR merges, drop /docs from the ZAP seeds and delete this row | /docs, /redoc and /openapi.json are disabled in production (fix/s5-policy, "disable OpenAPI docs in production"); API routes raise no medium alerts | 2026-11-12 | 2026-12-12 |
