# Scan exceptions

Findings from security scanners that are knowingly left unfixed. Every entry has an expiry, and CI fails when an entry is expired or its window is too long.

## Policy

- Upgrade first. An exception is only for a finding with no fixed version, or a fix that is a breaking major upgrade needing its own work.
- The maximum window is 90 days (`Expires` minus `Added`). Exactly 90 days is allowed.
- Renewing means a new `Added` date and a fresh justification. Extending `Expires` alone is not a renewal.
- An entry is valid through its `Expires` date and fails the day after.
- `pip-audit`, `trivy` and `semgrep` entries are suppressed in CI from this list (`python .github/scripts/scan_exceptions.py ids <scanner>`).
- `npm-audit`, `govulncheck` and `codeql` entries are recorded here but suppressed by other means: npm `overrides`, or a CodeQL dismissal whose comment cites the entry ID.
- Dates are `YYYY-MM-DD`. Scanner is one of `pip-audit`, `npm-audit`, `govulncheck`, `trivy`, `codeql`, `semgrep`, `alembic-check`.
- The `## Exceptions` section holds only the table (no code blocks, nothing after the table), and the checker rejects anything else.
- Do not put secrets or personal data in this file.

## Exceptions

| ID | Scanner | Package / location | Reason | Compensating control | Added | Expires |
| --- | --- | --- | --- | --- | --- | --- |
