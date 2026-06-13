"""Per-finding risk scorer (Month 3, Phase 3).

Distinct from the org-level ``risk_scoring.py`` (which scores a whole SMB from
industry + size signals). This module scores a *single* ``asset_finding`` — one
asset-software ↔ CVE pairing — on a 0-100 scale and maps it to a tier the UI
renders: ``Critical | High | Medium | Low | Needs Review``.

The score combines, in rough order of weight:

* **KEV** — known exploited in the wild dominates (large fixed boost).
* **CVSS** — technical severity, scaled to the score.
* **EPSS** — probability of exploitation in the next 30 days.
* **Internet exposure** — an internet-facing asset is reachable by attackers.
* **Asset criticality** — how much a compromise of *this* asset would hurt.
* **Exploit / disclosure recency** — freshly disclosed CVEs skew riskier.

``match_confidence`` is a **required modifier**, never optional: a ``needs_review``
match always returns the ``Needs Review`` tier regardless of the numeric score,
because a false ``high`` erodes trust permanently (roadmap principle). ``low``
confidence damps the score so weak name-only matches cannot present as Critical.

The scorer is a pure function so the Phase 5 regression harness and unit tests
can exercise every factor without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["high", "medium", "low", "needs_review"]
RiskTier = Literal["Critical", "High", "Medium", "Low", "Needs Review"]
AssetCriticality = Literal["low", "normal", "high", "critical"]

# Fixed boost for a CVE listed in CISA KEV — exploited in the wild outweighs
# any single technical factor.
_KEV_POINTS = 40.0

# CVSS contributes up to 35 points (base 0-10 → ×3.5).
_CVSS_WEIGHT = 3.5
_CVSS_MAX_POINTS = 35.0

# EPSS is a 0-1 probability; up to 15 points.
_EPSS_MAX_POINTS = 15.0

# Reachability and blast-radius modifiers.
_INTERNET_EXPOSED_POINTS = 10.0
_RECENT_DISCLOSURE_POINTS = 5.0
# Window (days) under which a CVE counts as "recently disclosed".
RECENT_DISCLOSURE_DAYS = 365

_CRITICALITY_POINTS: dict[str, float] = {
    "low": -5.0,
    "normal": 0.0,
    "high": 8.0,
    "critical": 15.0,
}

# Confidence multipliers applied to the *numeric* score. ``needs_review`` is
# handled separately (it forces the tier), so it has no multiplier here.
_CONFIDENCE_MULTIPLIER: dict[str, float] = {
    "high": 1.0,
    "medium": 0.85,
    "low": 0.6,
}


@dataclass(frozen=True)
class FindingRisk:
    """Result of scoring one finding."""

    score: float
    tier: RiskTier


def _tier_from_score(score: float) -> RiskTier:
    if score >= 80.0:
        return "Critical"
    if score >= 60.0:
        return "High"
    if score >= 35.0:
        return "Medium"
    return "Low"


def tier_for(confidence: str, score: float | None) -> RiskTier:
    """Derive the display tier for an already-persisted finding.

    Mirrors ``score_finding``'s tiering, including the ``needs_review`` override,
    without recomputing the score from raw factors.
    """
    if confidence == "needs_review":
        return "Needs Review"
    return _tier_from_score(score or 0.0)


def score_finding(
    *,
    confidence: Confidence,
    cvss_score: float | None,
    epss_score: float | None,
    kev_flag: bool,
    asset_criticality: str = "normal",
    internet_exposed: bool = False,
    days_since_disclosure: int | None = None,
) -> FindingRisk:
    """Score a single finding and assign a risk tier.

    ``confidence`` gates the result: ``needs_review`` short-circuits to the
    ``Needs Review`` tier (the numeric score is still computed for reference but
    never elevates the finding). Otherwise the raw 0-100 score is scaled by the
    confidence multiplier before being clamped and mapped to a tier.
    """
    score = 0.0

    if kev_flag:
        score += _KEV_POINTS

    if cvss_score is not None:
        clamped = max(0.0, min(cvss_score, 10.0))
        score += min(clamped * _CVSS_WEIGHT, _CVSS_MAX_POINTS)

    if epss_score is not None:
        clamped_epss = max(0.0, min(epss_score, 1.0))
        score += clamped_epss * _EPSS_MAX_POINTS

    if internet_exposed:
        score += _INTERNET_EXPOSED_POINTS

    if days_since_disclosure is not None and 0 <= days_since_disclosure <= RECENT_DISCLOSURE_DAYS:
        score += _RECENT_DISCLOSURE_POINTS

    score += _CRITICALITY_POINTS.get(asset_criticality, 0.0)

    # Never let a damping criticality push the score negative.
    score = max(0.0, score)

    if confidence == "needs_review":
        # A finding we cannot trust is surfaced for a human, not ranked.
        return FindingRisk(score=round(min(score, 100.0), 2), tier="Needs Review")

    score *= _CONFIDENCE_MULTIPLIER.get(confidence, 1.0)
    score = min(score, 100.0)
    return FindingRisk(score=round(score, 2), tier=_tier_from_score(score))
