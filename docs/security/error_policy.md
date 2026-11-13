# Error-message policy (T-PLAT-07)

Internal exception text (database errors, SDK errors, file paths) must not reach users.

## Policy

1. A 5xx response never carries exception text. Routes return a fixed `detail` such as `"Internal error"`. The global 500 handler returns a plain-text body pinned by `tests/test_security_headers.py`.
2. A 4xx `detail` may carry only app-authored text, never `str(exc)`.
3. A stored error field shown to users holds a class name or an app-authored bare identifier (for example `DuplicateScanSubmission`). Anything else renders as `"error"`.
4. Server logs carry the exception class and HTTP status only, through `safe_http_error` (`app/core/logging.py`), as `logger.warning("<fixed message>", <ids>, extra={"error": safe_http_error(exc)})`. The message text and traceback are not logged at these sites. That is a deliberate trade-off: less debugging context in exchange for no SQL, bound parameters or URLs in logs.
5. Out of scope here: ingest-run errors (T-ING-10), domain checks (T-DOM-08), and the M365 integration, which is disabled in production (T-PLAT-16). Known exceptions to points 1-2, left as follow-ups: `app/api/routes/v1/nvd.py` (422 `detail=str(e)` on a repository `ValueError`, line 89) and `app/api/routes/v1/assessments.py` (409/404 `detail=str(exc)`, lines 45, 103 and 105).

## How it is enforced

- `app/core/errors.py::public_error` reduces a stored error to a bare identifier (`[A-Za-z_][A-Za-z0-9_]*`) or `"error"`. It runs as a pydantic `field_validator` on `AISummaryGenerationListItem` (AI history) and `ScanRunRead` (scan runs), so it applies at the response layer.
- Rows written before this change are redacted on read. There is no data migration.
- Write sites store `type(exc).__name__` (AI summary generation, scan-run failures) or an app-authored bare identifier. App-authored stored text must be a bare identifier, or it renders as `"error"`.
- The vulnerabilities routes return `detail="Internal error"` on every 500 and log only the exception class and status (all branches, including the 503 fallbacks, no traceback).

## Tests

- `backend/tests/test_ai_summary_generation.py::test_history_response_has_no_raw_exception_text`
- `backend/tests/test_error_policy.py::test_scan_run_status_has_no_raw_exception_text`
- `backend/tests/test_error_policy.py::test_vulnerabilities_500_detail_is_generic`
