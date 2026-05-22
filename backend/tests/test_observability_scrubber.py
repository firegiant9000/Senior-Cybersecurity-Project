"""Guard the backend↔frontend Sentry scrubber list contract.

Both stacks duplicate the sensitive-key list (they cannot share a runtime
module). This test reads the TS source and asserts the two lists agree.
A drift here means one stack will leak a field the other side knows to
redact, so the test fails CI before that ships.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.observability import _SENSITIVE_KEY_PATTERNS

_FRONTEND_FILE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "observability.ts"
)


def _parse_ts_patterns(text: str) -> list[str]:
    """Extract entries of `const SENSITIVE_KEY_PATTERNS = [...]`."""
    match = re.search(
        r"const\s+SENSITIVE_KEY_PATTERNS\s*=\s*\[([^\]]+)\]",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(
            "could not locate SENSITIVE_KEY_PATTERNS in frontend/src/lib/observability.ts"
        )
    body = match.group(1)
    return re.findall(r"'([^']+)'", body)


def test_scrubber_lists_agree():
    if not _FRONTEND_FILE.exists():
        # Backend test runs in CI without the frontend tree checked out in
        # some configurations — skip rather than fail noisily.
        import pytest

        pytest.skip(f"frontend observability.ts not found at {_FRONTEND_FILE}")
    ts_patterns = _parse_ts_patterns(_FRONTEND_FILE.read_text(encoding="utf-8"))
    backend_set = set(_SENSITIVE_KEY_PATTERNS)
    ts_set = set(ts_patterns)
    only_backend = backend_set - ts_set
    only_frontend = ts_set - backend_set
    assert not only_backend and not only_frontend, (
        f"sensitive-key list drifted between stacks; "
        f"only in backend: {only_backend}; only in frontend: {only_frontend}"
    )
