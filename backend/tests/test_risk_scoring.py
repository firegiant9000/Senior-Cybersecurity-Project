"""Tests for backend/app/services/risk_scoring.py – issue #33."""

from unittest.mock import MagicMock

import pytest

from app.services.risk_scoring import basic_vuln_risk_score, calculate_risk_score

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
