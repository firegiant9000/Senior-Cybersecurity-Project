"""Month 3, Phase 5 — pytest entry point for the matcher regression harness.

Asserts the calibration gate (roadmap Checkpoint 2): the known-good set must
resolve at >= 95% pass rate with a < 2% high-confidence false-positive rate. The
nightly CI job runs this file; a regression in the matcher fails the gate here.
"""

from __future__ import annotations

import pytest

from tests.regression.matcher_known_good import (
    CASES,
    MAX_HIGH_CONF_FP_RATE,
    MIN_PASS_RATE,
    Case,
    evaluate,
    format_report,
    run_case,
)


def test_known_good_set_is_large_enough() -> None:
    # Phase 5 requires 50+ cases spanning all confidence tiers.
    assert len(CASES) >= 50
    tiers = {case.tier for case in CASES}
    assert {"high", "medium", "low", "needs_review", "negative"} <= tiers


@pytest.mark.asyncio
async def test_calibration_gate() -> None:
    report = await evaluate()
    assert report.gate_passed, "\n" + format_report(report)
    assert report.pass_rate >= MIN_PASS_RATE
    assert report.high_conf_fp_rate < MAX_HIGH_CONF_FP_RATE


@pytest.mark.asyncio
async def test_no_high_confidence_false_positives() -> None:
    # The roadmap's hardest line: a high-confidence false positive erodes trust
    # permanently. The known-good set is calibrated to produce zero.
    report = await evaluate()
    offenders = [
        (r.case.label, cve)
        for r in report.results
        for cve, conf in r.returned.items()
        if conf == "high" and cve not in r.case.expected
    ]
    assert not offenders, f"high-confidence false positives: {offenders}"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c.label for c in CASES])
async def test_each_known_good_case(case: Case) -> None:
    result = await run_case(case)
    assert result.passed, result.failure_reason
