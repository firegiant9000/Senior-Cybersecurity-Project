"""Deploy facts exposed by the public /health endpoints.

/health is unauthenticated, so everything here is validated and bounded:
a malformed environment value is never echoed back.
"""

import os
import re

from app.core.config import settings
from app.workers.scheduler import scheduler, source_cron_exprs

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_COMMIT_ENV_VARS = ("RENDER_GIT_COMMIT", "GIT_COMMIT")
_SHORT_LEN = 12


def deployed_commit() -> str:
    """Return the deployed commit as up to 12 lowercase hex chars, or "unknown"."""
    for name in _COMMIT_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if _SHA_RE.fullmatch(value):
            return value.lower()[:_SHORT_LEN]
    return "unknown"


def scheduler_state() -> tuple[bool, int]:
    """Return (scheduler enabled by config, number of ingest jobs while running).

    Only the ``ingest_<source>`` jobs count, so the catch-up sweep, matcher,
    CPE backfill and retention jobs cannot mask a missing ingest schedule.
    """
    if not scheduler.running:
        return settings.SCHEDULER_ENABLED, 0
    ingest_ids = {f"ingest_{source}" for source in source_cron_exprs()}
    jobs = sum(1 for job in scheduler.get_jobs() if job.id in ingest_ids)
    return settings.SCHEDULER_ENABLED, jobs
