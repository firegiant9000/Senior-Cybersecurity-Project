"""Risk scoring utilities."""

from app.db.models import CVE, KEV, EconomicIndicator, IC3Incident


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


def basic_vuln_risk_score(
    severity_score: float | None, *, exploited: bool
) -> float | None:
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
