"""Deterministic prompt-injection corpus for the AI summary (S5a item 6).

Every attack string from `evals.ai_summary.attack_strings.corpus()` (CI-only
canaries, never the dataset's) is placed in an org name and an industry
label. The tests check prompt *structure*, not the model:
- the hostile value reaches the prompt only inside the JSON data block;
- a mocked model that obeys the attack (the canary as a cited id, broken
  JSON) never gets the canary into the served response.

No network: `_call_gemini` is patched.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.findings import Finding, FindingsReport, FindingsSummary
from app.services import ai_summary
from evals.ai_summary.attack_strings import CI_CANARY_PREFIX, corpus

ATTACKS = corpus()
FIELDS = ("name", "industry_label")
CASES = [(field, a) for field in FIELDS for a in ATTACKS]
IDS = [f"{field}-{a.canary}" for field, a in CASES]


def test_corpus_is_large_enough_and_ci_only():
    assert len(CASES) >= 20
    assert all(a.canary.startswith(CI_CANARY_PREFIX) for a in ATTACKS)
    # The canary is assembled from two parts, so the joined token is never input.
    assert all(a.canary not in a.text for a in ATTACKS)


def _org(field: str, value: str):
    values = {
        "id": 777,
        "name": "Example Bakery LLC",
        "industry_label": "Retail Trade",
        "employee_range": "11-50",
        "primary_state": "OH",
    }
    values[field] = value
    return SimpleNamespace(**values)


def _report() -> FindingsReport:
    finding = Finding(
        id="f-real",
        finding_type="vendor_exposure",
        severity="critical",
        severity_score=90.0,
        title="Critical flaw in Example POS",
        description="A known-exploited vulnerability affects the POS terminal.",
        evidence={},
        source="kev_vendor_match",
        affected_assets=[],
    )
    return FindingsReport(
        org_id=777,
        findings=[finding],
        summary=FindingsSummary(total=1, by_type={}, by_severity={"critical": 1}),
        generated_at="2026-10-20T00:00:00",
        data_sources_used=[],
        assessment_tier="partial",
    )


def _split(prompt: str) -> tuple[str, dict, str]:
    """The text before the block, the parsed block, and the text after it."""
    lines = prompt.split("\n")
    # Exactly one BEGIN and one END line, so the block can't be forged.
    assert lines.count(ai_summary.DATA_BEGIN) == 1
    assert lines.count(ai_summary.DATA_END) == 1
    begin = prompt.index(f"\n{ai_summary.DATA_BEGIN}\n") + len(ai_summary.DATA_BEGIN) + 2
    end = prompt.index(f"\n{ai_summary.DATA_END}\n", begin)
    return prompt[:begin], json.loads(prompt[begin:end]), prompt[end:]


@pytest.mark.parametrize(("field", "attack"), CASES, ids=IDS)
def test_attack_reaches_the_prompt_only_inside_the_data_block(field, attack):
    hostile, _ = ai_summary._build_prompt(_org(field, attack.text), _report(), 50.0)
    benign, _ = ai_summary._build_prompt(_org(field, "Benign value"), _report(), 50.0)
    h_before, h_data, h_after = _split(hostile)
    b_before, _, b_after = _split(benign)

    assert h_data["organization"][field] == attack.text
    # The attack changes nothing outside the block.
    assert (h_before, h_after) == (b_before, b_after)


def _compliant_outputs(canary: str) -> dict[str, str]:
    """What a model that obeyed the attack might return."""
    risk = {"title": canary, "severity": "critical", "context": canary, "finding_ids": [canary]}
    base = {"posture_statement": "p", "data_gaps": [], "next_steps": []}
    return {
        "fake_id": json.dumps(base | {"narrative": "n", "notable_risks": [risk]}),
        "broken_json": '{"narrative": "' + canary + '", "notable_risks": [',
        "prose": f"{canary} {canary}",
    }


async def _serve(org, raw: str):
    db = MagicMock()
    snap = MagicMock()
    snap.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=snap)
    with (
        patch("app.services.ai_summary.FindingsEngine") as engine_cls,
        patch("app.services.ai_summary._get_feedback_meta", new=AsyncMock(return_value=None)),
        patch("app.services.ai_summary._call_gemini", new=AsyncMock(return_value=raw)),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as repo_cls,
    ):
        engine_cls.return_value.build = AsyncMock(return_value=_report())
        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_MODEL = "gemini-test"
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600
        repo = AsyncMock()
        repo.get_last_successful_gemini.return_value = None
        repo_cls.return_value = repo
        svc = ai_summary.AISummaryService(db)
        svc.invalidate(org.id)
        result = await svc.build(org)
        svc.invalidate(org.id)
    return result, repo.create.call_args.kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fake_id", "broken_json", "prose"])
@pytest.mark.parametrize(("field", "attack"), CASES, ids=IDS)
async def test_attack_compliant_output_never_serves_the_canary(field, attack, mode):
    raw = _compliant_outputs(attack.canary)[mode]
    result, stored = await _serve(_org(field, attack.text), raw)

    assert attack.canary not in result.model_dump_json()
    assert attack.canary not in (stored["output_text"] or "")
    assert attack.canary not in (stored["error_message"] or "")
