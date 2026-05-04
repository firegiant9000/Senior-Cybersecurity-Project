"""Tests for backend/app/services/risk_scoring.py – issue #33."""

from unittest.mock import MagicMock

import pytest

from app.services.risk_scoring import (
    basic_vuln_risk_score,
    calculate_risk_score,
    calculate_smb_risk_score,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cve(cvss: float) -> MagicMock:
    m = MagicMock()
    m.cvss_score = cvss
    return m


def _incidents(losses: list[float]) -> list[MagicMock]:
    return [MagicMock(loss_amount=amt) for amt in losses]


def _kev() -> MagicMock:
    """Return a truthy KEV-like mock."""
    return MagicMock()


def _econ(smb_count: int) -> MagicMock:
    m = MagicMock()
    m.smb_count = smb_count
    return m


# ---------------------------------------------------------------------------
# calculate_risk_score
# ---------------------------------------------------------------------------


class TestCalculateRiskScore:
    def test_all_none_empty(self):
        assert calculate_risk_score(None, None, [], None) == pytest.approx(0.0)

    def test_cve_only_cvss_10(self):
        assert calculate_risk_score(_cve(10.0), None, [], None) == pytest.approx(40.0)

    def test_cve_only_cvss_3(self):
        assert calculate_risk_score(_cve(3.0), None, [], None) == pytest.approx(30.0)

    def test_cve_plus_kev(self):
        assert calculate_risk_score(_cve(10.0), _kev(), [], None) == pytest.approx(70.0)

    def test_cve_kev_high_loss_incidents(self):
        incidents = _incidents([2_000_000, 3_000_000])
        assert calculate_risk_score(_cve(10.0), _kev(), incidents, None) == pytest.approx(90.0)

    def test_cve_kev_medium_loss_incidents(self):
        incidents = _incidents([200_000, 300_000])
        assert calculate_risk_score(_cve(10.0), _kev(), incidents, None) == pytest.approx(80.0)

    def test_all_factors_capped_at_100(self):
        incidents = _incidents([5_000_000])
        econ = _econ(100_000)
        assert calculate_risk_score(_cve(10.0), _kev(), incidents, econ) == pytest.approx(100.0)

    def test_kev_only_no_cve(self):
        assert calculate_risk_score(None, _kev(), [], None) == pytest.approx(30.0)

    def test_incidents_exactly_100k_no_bonus(self):
        incidents = _incidents([100_000])
        assert calculate_risk_score(None, None, incidents, None) == pytest.approx(0.0)

    def test_incidents_exactly_1_000_001_gives_20(self):
        incidents = _incidents([1_000_001])
        assert calculate_risk_score(None, None, incidents, None) == pytest.approx(20.0)

    def test_econ_smb_exactly_50000_no_bonus(self):
        assert calculate_risk_score(None, None, [], _econ(50_000)) == pytest.approx(0.0)

    def test_econ_smb_50001_gives_10(self):
        assert calculate_risk_score(None, None, [], _econ(50_001)) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# basic_vuln_risk_score
# ---------------------------------------------------------------------------


class TestBasicVulnRiskScore:
    def test_none_not_exploited_returns_none(self):
        assert basic_vuln_risk_score(None, exploited=False) is None

    def test_none_exploited_returns_30(self):
        assert basic_vuln_risk_score(None, exploited=True) == pytest.approx(30.0)

    def test_max_severity_exploited_returns_100(self):
        assert basic_vuln_risk_score(10.0, exploited=True) == pytest.approx(100.0)

    def test_mid_severity_not_exploited(self):
        assert basic_vuln_risk_score(5.0, exploited=False) == pytest.approx(35.0)

    def test_zero_severity_not_exploited(self):
        assert basic_vuln_risk_score(0.0, exploited=False) == pytest.approx(0.0)

    def test_above_max_clamped(self):
        # 15.0 clamped to 10.0 -> 10*7 = 70
        assert basic_vuln_risk_score(15.0, exploited=False) == pytest.approx(70.0)

    def test_negative_clamped_exploited(self):
        # -5.0 clamped to 0.0 -> 0*7 + 30 = 30
        assert basic_vuln_risk_score(-5.0, exploited=True) == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# calculate_smb_risk_score
# ---------------------------------------------------------------------------


class TestCalculateSmbRiskScore:
    def test_returns_response_object(self):
        result = calculate_smb_risk_score("Healthcare", "11-50")
        assert result.score >= 0.0
        assert result.score <= 100.0

    def test_known_industry_produces_nonzero_industry_score(self):
        result = calculate_smb_risk_score("Healthcare", "11-50")
        assert result.industry_exposure.industry_score > 0.0

    def test_unknown_industry_yields_zero_industry_score(self):
        result = calculate_smb_risk_score("Underwater Basket Weaving", "11-50")
        assert result.industry_exposure.industry_score == pytest.approx(0.0)

    def test_none_industry_yields_zero_industry_score(self):
        result = calculate_smb_risk_score(None, "11-50")
        assert result.industry_exposure.industry_score == pytest.approx(0.0)

    def test_employee_range_solo_gives_low_size_score(self):
        result = calculate_smb_risk_score(None, "1-10")
        assert result.size_factor.size_score == pytest.approx(10.0)

    def test_employee_range_large_enterprise_gives_high_size_score(self):
        result = calculate_smb_risk_score(None, "1001+")
        assert result.size_factor.size_score == pytest.approx(90.0)

    def test_none_employee_range_uses_default(self):
        result = calculate_smb_risk_score(None, None)
        assert result.size_factor.employee_range == "unknown"
        assert result.size_factor.size_score > 0.0

    def test_score_is_weighted_sum(self):
        result = calculate_smb_risk_score(None, "1-10")
        expected = round(
            result.industry_exposure.industry_score * 0.60 + result.size_factor.size_score * 0.40,
            2,
        )
        assert result.score == pytest.approx(expected)

    def test_breakdown_has_two_components(self):
        result = calculate_smb_risk_score("Finance & Insurance", "201-500")
        assert len(result.breakdown) == 2
        names = {c.name for c in result.breakdown}
        assert "Industry Exposure" in names
        assert "Size Factor" in names

    def test_score_never_exceeds_100(self):
        result = calculate_smb_risk_score("Finance & Insurance", "1001+")
        assert result.score <= 100.0

    def test_industry_exposure_items_sorted_descending(self):
        result = calculate_smb_risk_score("Healthcare", "51-200")
        contributions = [i.contribution for i in result.industry_exposure.items]
        assert contributions == sorted(contributions, reverse=True)

    def test_methodology_field_present(self):
        result = calculate_smb_risk_score("Healthcare", "11-50")
        assert len(result.methodology) > 50

    def test_generated_at_is_iso_string(self):
        result = calculate_smb_risk_score(None, None)
        assert "T" in result.generated_at  # basic ISO 8601 check


# ---------------------------------------------------------------------------
# Remediation credit
# ---------------------------------------------------------------------------


class TestRemediationCredit:
    """Remediation credit derived from done-state findings deducts from the
    org's risk score. Behaviour cap is 75% of base; per-severity weights are
    tuned so a single critical = ~2.5 pts."""

    def _items(self, *severities: str):
        from app.schemas.smb_risk_score import RemediatedItem

        return [
            RemediatedItem(stable_key=f"k{i}", title=f"finding {i}", severity=sev)
            for i, sev in enumerate(severities)
        ]

    def test_zero_items_returns_zero_credit(self):
        from app.services.risk_scoring import compute_remediation_credit

        credit = compute_remediation_credit([], 50.0)
        assert credit.done_count == 0
        assert credit.raw_points == 0.0
        assert credit.applied_points == 0.0
        assert credit.items == []

    def test_severity_weighting_orders_correctly(self):
        from app.services.risk_scoring import compute_remediation_credit

        crit = compute_remediation_credit(self._items("critical"), 100.0).raw_points
        high = compute_remediation_credit(self._items("high"), 100.0).raw_points
        med = compute_remediation_credit(self._items("medium"), 100.0).raw_points
        low = compute_remediation_credit(self._items("low"), 100.0).raw_points
        info = compute_remediation_credit(self._items("info"), 100.0).raw_points
        assert crit > high > med > low > info > 0

    def test_unknown_severity_falls_back_to_low_weight(self):
        from app.services.risk_scoring import compute_remediation_credit

        # Bogus severity should not break the calculation; treated as a
        # very-low-weight item rather than e.g. a crash or critical credit.
        credit = compute_remediation_credit(self._items("not-a-severity"), 100.0)
        assert credit.applied_points > 0
        assert credit.applied_points < 1.0  # bounded below "low"

    def test_credit_is_capped_at_75pct_of_base(self):
        from app.services.risk_scoring import compute_remediation_credit

        # 30 critical findings would naively be 75 raw points; cap at 75%
        # of base 50 = 37.5 forces applied_points to plateau there.
        many = self._items(*(["critical"] * 30))
        credit = compute_remediation_credit(many, 50.0)
        assert credit.raw_points > 37.5  # raw exceeds cap
        assert credit.applied_points == pytest.approx(37.5, abs=0.01)

    def test_effective_score_reflects_credit(self):
        from app.services.risk_scoring import (
            calculate_smb_risk_score,
            compute_remediation_credit,
        )

        base = calculate_smb_risk_score("Healthcare", "51-200")
        credit = compute_remediation_credit(self._items("critical", "high"), base.score)
        result = calculate_smb_risk_score(
            "Healthcare", "51-200", remediation_credit=credit
        )
        assert result.effective_score == pytest.approx(
            max(0.0, base.score - credit.applied_points), abs=0.01
        )
        assert result.remediation_credit.done_count == 2
        assert len(result.remediation_credit.items) == 2

    def test_effective_score_never_negative(self):
        from app.services.risk_scoring import (
            calculate_smb_risk_score,
            compute_remediation_credit,
        )

        # Tiny base + many criticals shouldn't underflow into negative space.
        # (Cap clamps applied_points before subtraction; defence-in-depth
        # check protects against future tuning changes.)
        many = self._items(*(["critical"] * 50))
        credit = compute_remediation_credit(many, 5.0)
        result = calculate_smb_risk_score(None, None, remediation_credit=credit)
        assert result.effective_score >= 0.0
