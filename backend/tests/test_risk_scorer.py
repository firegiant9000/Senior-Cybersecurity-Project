"""Phase 3 (Month 3) — per-finding risk scorer unit tests.

Locks in the factor weighting and, critically, the confidence gating: a
``needs_review`` match must never present as Critical, and ``low`` confidence
must damp an otherwise-high score. These guard the roadmap principle that a
false high-confidence finding erodes trust permanently.
"""

from __future__ import annotations

import pytest

from app.services.risk_scorer import RECENT_DISCLOSURE_DAYS, score_finding, tier_for


def test_kev_critical_is_top_tier() -> None:
    risk = score_finding(
        confidence="high",
        cvss_score=9.8,
        epss_score=0.9,
        kev_flag=True,
    )
    assert risk.tier == "Critical"
    assert risk.score >= 80.0


def test_low_cvss_no_kev_is_low_tier() -> None:
    risk = score_finding(
        confidence="high",
        cvss_score=2.0,
        epss_score=0.0,
        kev_flag=False,
    )
    assert risk.tier == "Low"


def test_needs_review_never_elevates_even_with_kev() -> None:
    risk = score_finding(
        confidence="needs_review",
        cvss_score=10.0,
        epss_score=1.0,
        kev_flag=True,
        asset_criticality="critical",
        internet_exposed=True,
    )
    assert risk.tier == "Needs Review"


def test_low_confidence_damps_score() -> None:
    high = score_finding(confidence="high", cvss_score=8.0, epss_score=0.5, kev_flag=True)
    low = score_finding(confidence="low", cvss_score=8.0, epss_score=0.5, kev_flag=True)
    assert low.score < high.score


def test_internet_exposure_and_criticality_increase_score() -> None:
    base = score_finding(confidence="high", cvss_score=6.0, epss_score=0.1, kev_flag=False)
    boosted = score_finding(
        confidence="high",
        cvss_score=6.0,
        epss_score=0.1,
        kev_flag=False,
        asset_criticality="critical",
        internet_exposed=True,
    )
    assert boosted.score > base.score


def test_low_criticality_damps_score() -> None:
    normal = score_finding(confidence="high", cvss_score=6.0, epss_score=0.1, kev_flag=False)
    low_crit = score_finding(
        confidence="high",
        cvss_score=6.0,
        epss_score=0.1,
        kev_flag=False,
        asset_criticality="low",
    )
    assert low_crit.score < normal.score


def test_recent_disclosure_adds_points_only_within_window() -> None:
    recent = score_finding(
        confidence="high", cvss_score=5.0, epss_score=0.0, kev_flag=False, days_since_disclosure=10
    )
    old = score_finding(
        confidence="high",
        cvss_score=5.0,
        epss_score=0.0,
        kev_flag=False,
        days_since_disclosure=RECENT_DISCLOSURE_DAYS + 100,
    )
    assert recent.score > old.score


def test_missing_signals_score_zero_low() -> None:
    risk = score_finding(confidence="low", cvss_score=None, epss_score=None, kev_flag=False)
    assert risk.score == 0.0
    assert risk.tier == "Low"


def test_score_is_clamped_to_100() -> None:
    risk = score_finding(
        confidence="high",
        cvss_score=10.0,
        epss_score=1.0,
        kev_flag=True,
        asset_criticality="critical",
        internet_exposed=True,
        days_since_disclosure=1,
    )
    assert risk.score <= 100.0


@pytest.mark.parametrize(
    ("confidence", "score", "expected"),
    [
        ("needs_review", 95.0, "Needs Review"),
        ("high", 85.0, "Critical"),
        ("high", 65.0, "High"),
        ("high", 40.0, "Medium"),
        ("high", 10.0, "Low"),
        ("medium", None, "Low"),
    ],
)
def test_tier_for_mirrors_scoring(confidence: str, score: float | None, expected: str) -> None:
    assert tier_for(confidence, score) == expected
