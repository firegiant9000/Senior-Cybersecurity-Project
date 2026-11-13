# Error-message policy (T-PLAT-07)

Internal exception text (database errors, SDK errors, file paths) must not reach users.

## Policy

1. A 5xx response never carries exception text. Routes return a fixed `detail` such as `"Internal error"`. The global 500 handler returns a plain-text body pinned by `tests/test_security_headers.py`.
2. A 4xx `detail` may carry only app-authored text, never `str(exc)`.
3. A stored error field shown to users holds a class name or an app-authored bare identifier (for example `DuplicateScanSubmission`). Anything else renders as `"error"`.
4. The full detail goes to server logs through `safe_http_error` (`app/core/logging.py`), as `logger.warning("<fixed message>", <ids>, extra={"error": safe_http_error(exc)})`. Tracebacks are no longer logged at these sites (class and status only). That is a deliberate trade-off: less debugging context in exchange for no raw text in logs.
5. Out of scope here: ingest-run errors (T-ING-10), domain checks (T-DOM-08), and the M365 integration, which is disabled in production (T-PLAT-16).

## How it is enforced

- `app/core/errors.py::public_error` reduces a stored error to a bare identifier (`[A-Za-z_][A-Za-z0-9_]*`) or `"error"`. It runs as a pydantic `field_validator` on `AISummaryGenerationListItem` (AI history) and `ScanRunRead` (scan runs), so it applies at the response layer.
- Rows written before this change are redacted on read. There is no data migration.
- Write sites store `type(exc).__name__` (AI summary generation, scan-run failures) or an app-authored bare identifier. App-authored stored text must be a bare identifier, or it renders as `"error"`.
- The vulnerabilities routes return `detail="Internal error"` on 500 and log the cause.

## Tests

- `backend/tests/test_ai_summary_generation.py::test_history_response_has_no_raw_exception_text`
- `backend/tests/test_error_policy.py::test_scan_run_status_has_no_raw_exception_text`
- `backend/tests/test_error_policy.py::test_vulnerabilities_500_detail_is_generic`
