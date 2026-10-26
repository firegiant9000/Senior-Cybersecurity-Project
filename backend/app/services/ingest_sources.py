"""Per-source refresh policy for ingest.

``scheduled`` sources are refreshed on a cron and judged for staleness.
``static`` sources are never re-run for age: IC3 is static because its data is
the 2021-2025 annual-report seed, so there is nothing newer to fetch. A static
source is still seeded when its table is empty.

This module must not import from ``ingest_catchup`` (which imports it).
"""

from collections.abc import Mapping
from typing import Literal

RefreshPolicy = Literal["scheduled", "static"]

REFRESH_POLICIES: Mapping[str, RefreshPolicy] = {
    "nvd": "scheduled",
    "cisa_kev": "scheduled",
    "epss": "scheduled",
    "economics": "scheduled",
    "ic3": "static",
}


def refresh_policy(source: str) -> RefreshPolicy:
    """Policy for ``source``; an unknown source is ``scheduled`` so it is judged, not hidden."""
    return REFRESH_POLICIES.get(source, "scheduled")
