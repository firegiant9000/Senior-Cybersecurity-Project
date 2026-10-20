"""Pricing schema and cost formula (protocol §4, §6)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.ai_summary.pricing import TEMPLATE_PATH, Pricing, call_cost_usd, load_pricing

_VERIFIED = """\
model: gemini-2.5-flash
currency: USD
verified: true
checked_on: 2026-10-20
source_url: https://ai.google.dev/gemini-api/docs/pricing
input_per_1m_tokens: 0.30
output_per_1m_tokens: 2.50
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "pricing.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_template_is_marked_unverified():
    pricing = load_pricing(TEMPLATE_PATH)
    assert pricing.verified is False
    assert pricing.model == "gemini-2.5-flash"


def test_verified_file_loads(tmp_path):
    pricing = load_pricing(_write(tmp_path, _VERIFIED))
    assert pricing.verified is True
    assert str(pricing.checked_on) == "2026-10-20"


@pytest.mark.parametrize("key", ["checked_on", "source_url"])
def test_verified_file_needs_date_and_source(tmp_path, key):
    text = "\n".join(line for line in _VERIFIED.splitlines() if not line.startswith(f"{key}:"))
    with pytest.raises(ValidationError):
        load_pricing(_write(tmp_path, text))


def test_rejects_unknown_key(tmp_path):
    with pytest.raises(ValidationError):
        load_pricing(_write(tmp_path, _VERIFIED + "discount: 0.5\n"))


def test_cost_formula_bills_thinking_as_output():
    pricing = Pricing(
        model="m",
        currency="USD",
        verified=False,
        input_per_1m_tokens=0.30,
        output_per_1m_tokens=2.50,
    )
    cost = call_cost_usd(pricing, prompt_tokens=2000, candidates_tokens=400, thoughts_tokens=100)
    assert cost == pytest.approx(2000 * 0.30 / 1e6 + 500 * 2.50 / 1e6)
