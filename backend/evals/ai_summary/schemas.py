"""The response schemas eval runs requested, so each run is scored against its own.

Schema-valid (protocol §4) means "parses into the schema the run asked for".
B0 and B1 asked for the pre-stage-D `StructuredSummary`, which has no
`finding_ids`; scoring them against today's schema would fail every output
for a field they were never asked to send. So this module keeps a frozen copy
of that v1 shape, and `run_eval` records the SHA-256 of the schema each new
run requests (`response_schema_sha256` in `run_meta.json`).

Citation-valid and KEV coverage read `finding_ids` in every run, whatever its
schema, so B0/B1 cite nothing: KEV coverage is 0 there by construction.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from app.schemas.ai_summary import GapItem, StepItem
from app.schemas.ai_summary import StructuredSummary as CurrentStructuredSummary


def schema_sha256(model: type[BaseModel]) -> str:
    return hashlib.sha256(
        json.dumps(model.model_json_schema(), sort_keys=True).encode()
    ).hexdigest()


# FROZEN: the shape B0 and B1 requested (app/schemas/ai_summary.py before stage
# D). The class names and the lack of docstrings are part of the hash; a test
# pins it to the hash those runs' provisional scores recorded.
class RiskItem(BaseModel):
    title: str
    severity: str
    context: str


class StructuredSummary(BaseModel):
    narrative: str
    posture_statement: str
    notable_risks: list[RiskItem]
    data_gaps: list[GapItem]
    next_steps: list[StepItem]


StructuredSummaryV1 = StructuredSummary

_KNOWN = {
    schema_sha256(StructuredSummaryV1): ("StructuredSummaryV1", StructuredSummaryV1),
    schema_sha256(CurrentStructuredSummary): ("StructuredSummary", CurrentStructuredSummary),
}


def requested_schema(meta: dict) -> tuple[str, type[BaseModel]]:
    """(name, model) of the response schema a run requested.

    Runs from before stage D record no schema; they all requested v1.
    """
    sha = meta.get("response_schema_sha256")
    if sha is None:
        return _KNOWN[schema_sha256(StructuredSummaryV1)]
    if sha not in _KNOWN:
        raise ValueError(
            "the run requested a response schema this scorer doesn't know "
            "(add a frozen copy here before scoring it)"
        )
    return _KNOWN[sha]
