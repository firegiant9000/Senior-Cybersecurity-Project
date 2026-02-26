"""Risk scoring utilities."""

from app.db.models import CVE, EconomicIndicator, IC3Incident, KEV

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


def basic_vuln_risk_score(severity_score: float | None, exploited: bool) -> float | None:
    """Basic risk score from CVSS severity and exploitation flag.

    The score is normalised to a 0–100 scale:

    - Up to 70 points from CVSS base score (0.0–10.0) scaled linearly.
    - +30 points if the vulnerability is known to be exploited (e.g. in KEV).

    Returns ``None`` when no CVSS score is available so callers can
    decide how to handle unknown risk.
    """
    if severity_score is None:
        return None

    base_component = max(0.0, min(severity_score, 10.0)) * 7.0
    exploited_component = 30.0 if exploited else 0.0
    return min(base_component + exploited_component, 100.0)
