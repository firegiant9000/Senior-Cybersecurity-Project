"""Stdlib stats for the eval report (protocol §5)."""

import pytest

from evals.ai_summary.stats import NOT_TESTABLE, flips, mcnemar_exact, wilson


def test_wilson_zero_of_22_upper_bound():
    lo, hi = wilson(0, 22)
    assert lo == 0.0
    assert hi == pytest.approx(0.149, abs=0.0005)


def test_wilson_all_successes_mirrors_zero():
    lo, hi = wilson(22, 22)
    assert hi == pytest.approx(1.0)
    assert lo == pytest.approx(1 - 0.149, abs=0.0005)


def test_wilson_known_midpoint_value():
    # 10/20 at 95%: (0.299, 0.701)
    lo, hi = wilson(10, 20)
    assert lo == pytest.approx(0.2993, abs=0.0005)
    assert hi == pytest.approx(0.7007, abs=0.0005)


def test_wilson_rejects_bad_counts():
    with pytest.raises(ValueError):
        wilson(0, 0)
    with pytest.raises(ValueError):
        wilson(3, 2)
    with pytest.raises(ValueError):
        wilson(-1, 2)


def test_mcnemar_five_discordant_not_testable():
    result = mcnemar_exact(5, 0)
    assert result.testable is False
    assert result.p_value is None
    assert result.note == NOT_TESTABLE


def test_mcnemar_six_discordant_one_direction():
    result = mcnemar_exact(6, 0)
    assert result.testable is True
    assert result.p_value == pytest.approx(0.03125)


def test_mcnemar_is_symmetric_and_capped():
    assert mcnemar_exact(0, 6).p_value == pytest.approx(0.03125)
    assert mcnemar_exact(4, 4).p_value == pytest.approx(1.0)


def test_mcnemar_known_value():
    # b=8, c=2, n=10: 2 * P(X<=2) = 2 * 56/1024
    assert mcnemar_exact(8, 2).p_value == pytest.approx(0.109375)


def test_flips_classifies_each_case():
    before = {"a": False, "b": True, "c": True, "d": False}
    after = {"a": True, "b": False, "c": True, "d": False}
    result = flips(before, after)
    assert result.fixed == ["a"]
    assert result.broke == ["b"]
    assert result.unchanged_pass == ["c"]
    assert result.unchanged_fail == ["d"]
    assert (result.b, result.c) == (1, 1)


def test_flips_requires_the_same_cases():
    with pytest.raises(ValueError, match="same cases"):
        flips({"a": True}, {"b": True})
