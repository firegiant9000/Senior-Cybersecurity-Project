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
