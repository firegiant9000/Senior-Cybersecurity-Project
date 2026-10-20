"""Price table schema and per-call cost (protocol §4 cost, §6 spend).

A dated, verified `pricing-YYYY-MM-DD.yaml` is required for any real run; the
committed template is unverified and only valid for dry runs.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.ai_summary.config import HERE, load_yaml_mapping

TEMPLATE_PATH = HERE / "pricing-TEMPLATE.yaml"


class Pricing(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    verified: bool
    checked_on: dt.date | None = None
    source_url: str | None = None
    input_per_1m_tokens: float = Field(ge=0)
    # Thinking tokens bill at the output rate.
    output_per_1m_tokens: float = Field(ge=0)

    @model_validator(mode="after")
    def _verified_needs_provenance(self) -> Pricing:
        if self.verified and (self.checked_on is None or not self.source_url):
            raise ValueError("verified pricing needs checked_on and source_url")
        return self


def load_pricing(path: Path) -> Pricing:
    return Pricing.model_validate(load_yaml_mapping(path))


def call_cost_usd(
    pricing: Pricing, *, prompt_tokens: int, candidates_tokens: int, thoughts_tokens: int
) -> float:
    """prompt × input price + (candidates + thoughts) × output price (§4)."""
    return (
        prompt_tokens * pricing.input_per_1m_tokens
        + (candidates_tokens + thoughts_tokens) * pricing.output_per_1m_tokens
    ) / 1_000_000
