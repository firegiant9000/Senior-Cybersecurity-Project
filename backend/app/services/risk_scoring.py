"""Risk scoring utilities."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.enums import INDUSTRY_TO_IC3_SECTOR, EmployeeRange, IndustryLabel
from app.db.models import CVE, KEV, EconomicIndicator, IC3Incident
from app.ingestors.ic3_real import ATTACK_SECTOR_WEIGHTS
from app.schemas.smb_risk_score import (
    AttackExposureItem,
    IndustryExposureDetail,
    RiskScoreResponse,
    ScoreComponent,
    SizeFactorDetail,
)

# Pre-build {attack_type: {sector: weight}} so we don't reconstruct dicts
# on every request.
_SECTOR_WEIGHT_DICTS: dict[str, dict[str, float]] = {
    attack_type: dict(sector_list) for attack_type, sector_list in ATTACK_SECTOR_WEIGHTS.items()
}

# ---------------------------------------------------------------------------
# Employee-range → size score (0-100 scale for risk contribution)
# Mirrors the incident-rate logic in loss_projection.py but normalized to a
# 0-100 scale where SOLO = 10 and LARGE_ENTERPRISE = 90.
# ---------------------------------------------------------------------------
_SIZE_SCORE: dict[str, float] = {
    EmployeeRange.SOLO: 10.0,
    EmployeeRange.SMALL: 25.0,
    EmployeeRange.MEDIUM: 45.0,
    EmployeeRange.LARGE: 65.0,
    EmployeeRange.ENTERPRISE: 80.0,
    EmployeeRange.LARGE_ENTERPRISE: 90.0,
}

_INCIDENT_RATE: dict[str, float] = {
    EmployeeRange.SOLO: 0.3,
    EmployeeRange.SMALL: 0.8,
    EmployeeRange.MEDIUM: 1.5,
    EmployeeRange.LARGE: 3.0,
    EmployeeRange.ENTERPRISE: 5.0,
    EmployeeRange.LARGE_ENTERPRISE: 9.0,
}

_METHODOLOGY = (
    "SMB risk score is a composite of two factors: "
    "(1) Industry Exposure (60% weight) — derived from FBI IC3 sector-attack weight "
    "tables, averaged across all known attack types to produce a normalized 0-100 "
    "industry exposure score; "
    "(2) Size Factor (40% weight) — maps the organization's employee range to a "
    "0-100 scale based on Verizon DBIR incident-rate data for companies of that size. "
    "The final score is the weighted sum, clamped to 0-100. "
    "Higher scores indicate greater expected exposure to cybercrime financial losses."
)


def calculate_risk_score(
    cve: CVE | None,
    kev: KEV | None,
    incidents: list[IC3Incident],
    econ: EconomicIndicator | None,
) -> float:
    """Calculate a composite risk score from threat context."""
    score = 0.0

    # Severity
    if cve and cve.cvss_score:
        score += min(cve.cvss_score * 10, 40)

    # Exploited in the wild
    if kev:
        score += 30

    # Historical financial impact
    if incidents:
        avg_loss = sum(i.loss_amount for i in incidents) / len(incidents)
        if avg_loss > 1_000_000:
            score += 20
        elif avg_loss > 100_000:
            score += 10

    # SMB economic sensitivity
    if econ and econ.smb_count > 50_000:
        score += 10

    return min(score, 100.0)


def basic_vuln_risk_score(severity_score: float | None, *, exploited: bool) -> float | None:
    """Return a simple 0-100 risk score from CVSS and exploitation status.

    - CVSS contributes up to 70 points (score * 7)
    - Known exploitation contributes 30 points
    - If CVSS is unknown, exploitation alone yields 30, else None
    """
    if severity_score is None:
        return 30.0 if exploited else None

    base_component = max(0.0, min(severity_score, 10.0)) * 7.0
    exploited_component = 30.0 if exploited else 0.0
    return min(base_component + exploited_component, 100.0)


def calculate_smb_risk_score(
    industry_label: str | None,
    employee_range: str | None,
) -> RiskScoreResponse:
    """Return a parameterized SMB risk score based on org industry and size.

    The score is a weighted composite:
      - Industry Exposure (60%): derived from ATTACK_SECTOR_WEIGHTS across all
        attack types for the given sector.
      - Size Factor (40%): maps employee_range to a 0-100 scale.
    """
    # ── Industry exposure ──────────────────────────────────────────────────────
    # Map the org's friendly IndustryLabel to its IC3 sector name used in
    # ATTACK_SECTOR_WEIGHTS (e.g. "Finance & Insurance" → "Finance").
    ic3_sector: str | None = None
    if industry_label:
        try:
            ic3_sector = INDUSTRY_TO_IC3_SECTOR.get(IndustryLabel(industry_label))
        except ValueError:
            ic3_sector = None

    sector = ic3_sector
    exposure_items: list[AttackExposureItem] = []

    total_weight_sum = 0.0
    count = 0

    for attack_type, sector_dict in _SECTOR_WEIGHT_DICTS.items():
        weight = sector_dict.get(sector, 0.0) if sector else 0.0
        contribution = weight * 100.0
        total_weight_sum += contribution
        count += 1
        exposure_items.append(
            AttackExposureItem(
                attack_type=attack_type,
                sector_weight=weight,
                contribution=contribution,
            )
        )

    industry_score = (total_weight_sum / count) if count > 0 else 0.0
    industry_score = min(industry_score, 100.0)

    industry_exposure = IndustryExposureDetail(
        sector=industry_label,
        items=sorted(exposure_items, key=lambda x: x.contribution, reverse=True),
        industry_score=round(industry_score, 2),
    )

    # ── Size factor ────────────────────────────────────────────────────────────
    size_score = _SIZE_SCORE.get(employee_range or "", 25.0)
    incident_rate = _INCIDENT_RATE.get(employee_range or "", 0.8)

    size_factor = SizeFactorDetail(
        employee_range=employee_range or "unknown",
        incident_rate=incident_rate,
        size_score=size_score,
    )

    # ── Weighted composite ─────────────────────────────────────────────────────
    industry_weight = 0.60
    size_weight = 0.40
    weighted_industry = industry_score * industry_weight
    weighted_size = size_score * size_weight
    final_score = min(weighted_industry + weighted_size, 100.0)

    breakdown = [
        ScoreComponent(
            name="Industry Exposure",
            score=round(industry_score, 2),
            weight=industry_weight,
            weighted_score=round(weighted_industry, 2),
        ),
        ScoreComponent(
            name="Size Factor",
            score=round(size_score, 2),
            weight=size_weight,
            weighted_score=round(weighted_size, 2),
        ),
    ]

    return RiskScoreResponse(
        score=round(final_score, 2),
        industry_exposure=industry_exposure,
        size_factor=size_factor,
        breakdown=breakdown,
        methodology=_METHODOLOGY,
        generated_at=datetime.now(UTC).isoformat(),
    )
