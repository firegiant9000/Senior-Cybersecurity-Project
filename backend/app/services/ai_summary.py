"""AI Executive Summary Service.

Feeds structured findings into Google Gemini to produce a plain-language
executive summary. Falls back to a template-based summary if Gemini is
unavailable or disabled.

Cache: in-memory per org_id, keyed by org_id. TTL from settings.AI_SUMMARY_CACHE_TTL.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.organization import Organization
from app.schemas.ai_summary import AISummaryResponse
from app.schemas.findings import FindingsReport
from app.services.disclaimers import DisclaimerContext, get_disclaimer
from app.services.findings_engine import FindingsEngine
from app.repositories.ai_summary_generation import SqlAISummaryGenerationRepository
from app.services.risk_scoring import calculate_smb_risk_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: {org_id: (timestamp, AISummaryResponse)}
# ---------------------------------------------------------------------------
_cache: dict[int, tuple[float, AISummaryResponse]] = {}


def _risk_label(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def _format_loss(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(
    org: Organization,
    report: FindingsReport,
    risk_score: float,
    *,
    feedback_hint: str | None = None,
) -> tuple[str, dict[str, Any]]:
    label = _risk_label(risk_score)

    # Summarize findings as structured JSON — org name/vendor names are
    # inserted into a data block, not freeform text, to limit injection risk.
    findings_summary: list[dict[str, Any]] = []
    for f in report.findings[:20]:  # cap at 20 to stay within token budget
        findings_summary.append(
            {
                "type": f.finding_type,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
            }
        )

    critical_count = report.summary.by_severity.get("critical", 0)
    high_count = report.summary.by_severity.get("high", 0)
    readiness_pct = _readiness_pct(report)

    system_block = (
        "You are a cybersecurity risk analyst writing a brief executive summary.\n"
        "You MUST only reference data provided below. Do NOT speculate or invent threats.\n"
        "Write in a professional, non-alarmist, actionable tone.\n"
        "Use 3-5 short paragraphs."
    )

    context_block = (
        f"Organization: {org.name or 'Unknown'}\n"
        f"Industry: {org.industry_label or 'Unknown'}\n"
        f"Size: {org.employee_range or 'Unknown'} employees\n"
        f"State: {org.primary_state or 'Unknown'}"
    )

    metrics_block = (
        f"Risk Score: {risk_score:.0f}/100 ({label})\n"
        f"Critical Findings: {critical_count}\n"
        f"High Findings: {high_count}\n"
        f"Total Findings: {report.summary.total}\n"
        f"Assessment Completeness: {readiness_pct}%"
    )

    instructions = (
        "1. Open with a one-sentence overall risk posture statement.\n"
        "2. Highlight the top 2-3 most actionable findings with context.\n"
        "3. Explain vendor exposure in business terms (not CVE IDs).\n"
        "4. Note the most impactful data gaps and how filling them improves the assessment.\n"
        "5. Close with 3 prioritized next steps the organization should take.\n\n"
        "Do NOT mention specific CVE identifiers. Refer to vulnerabilities by vendor, "
        "product, and severity. Keep the total response under 500 words."
    )

    feedback_block = ""
    if feedback_hint:
        feedback_block = f"\nUSER FEEDBACK ON PREVIOUS SUMMARIES:\n{feedback_hint}\n"

    prompt_str = (
        f"{system_block}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"STRUCTURED FINDINGS:\n{json.dumps(findings_summary, indent=2)}\n\n"
        f"RISK METRICS:\n{metrics_block}\n"
        f"{feedback_block}\n"
        f"INSTRUCTIONS:\n{instructions}"
    )

    prompt_inputs: dict[str, Any] = {
        "org": {
            "name": org.name,
            "industry": org.industry_label,
            "employee_range": org.employee_range,
            "state": org.primary_state,
        },
        "risk_metrics": {
            "risk_score": risk_score,
            "risk_label": label,
            "critical_count": critical_count,
            "high_count": high_count,
            "total_findings": report.summary.total,
            "assessment_completeness_pct": readiness_pct,
        },
        "findings": findings_summary,
        "feedback_hint": feedback_hint,
    }

    return prompt_str, prompt_inputs


def _readiness_pct(report: FindingsReport) -> int:
    """Estimate completeness % from assessment tier."""
    tier_map = {"minimal": 25, "partial": 50, "good": 75, "complete": 100, "comprehensive": 100}
    return tier_map.get(report.assessment_tier, 50)


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------


def _build_fallback(org: Organization, report: FindingsReport, risk_score: float) -> str:
    label = _risk_label(risk_score)
    name = org.name or "Your organization"
    industry = org.industry_label or "your industry"
    size = org.employee_range or "unknown size"
    critical_count = report.summary.by_severity.get("critical", 0)
    total = report.summary.total

    threat_findings = [
        f
        for f in report.findings
        if f.finding_type == "threat_exposure" and f.severity in ("critical", "high")
    ]
    top_threats = [f.title for f in threat_findings[:2]]
    threats_text = (
        f"Primary threat exposures include: {'; '.join(top_threats)}."
        if top_threats
        else "No high-severity threat exposures were identified at this time."
    )

    vendor_findings = [
        f
        for f in report.findings
        if f.finding_type == "vendor_exposure" and f.severity == "critical"
    ]
    vendor_text = (
        f"Your technology stack has {critical_count} critical known-exploited "
        "vulnerabilities requiring immediate attention."
        if vendor_findings
        else "No critical vendor vulnerabilities were matched at this time."
    )

    data_gaps = [
        f for f in report.findings if f.finding_type == "data_gap" and f.evidence.get("required")
    ]
    gap_text = (
        f"Completing {len(data_gaps)} required profile field(s) would significantly "
        "improve assessment accuracy and enable additional analysis."
        if data_gaps
        else "Your organization profile is well-populated, enabling comprehensive analysis."
    )

    recs = [f for f in report.findings if f.finding_type == "recommended_action"]
    rec_text = (
        "Recommended next steps: " + " | ".join(r.title for r in recs[:3]) + "."
        if recs
        else "Continue monitoring the platform for new threat intelligence updates."
    )

    return (
        f"Based on our analysis, {name} has an overall risk score of {risk_score:.0f}/100 ({label}). "
        f"As a {size}-employee organization in {industry}, this assessment covers {total} findings "
        f"across threat exposure, vendor vulnerabilities, and profile completeness.\n\n"
        f"{threats_text}\n\n"
        f"{vendor_text}\n\n"
        f"{gap_text}\n\n"
        f"{rec_text}"
    )


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------


def _call_gemini_sync(prompt: str) -> str:
    """Call Gemini (sync SDK) and return the text."""
    import google.generativeai as genai  # imported lazily to avoid hard dependency

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text


async def _call_gemini(prompt: str) -> str:
    """Run the sync Gemini call in a thread pool to avoid blocking the event loop."""
    import asyncio
    from functools import partial

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_call_gemini_sync, prompt))


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


async def _get_feedback_meta(db: AsyncSession, org_id: int) -> str | None:
    """Aggregate recent feedback to inject as a meta-instruction in the prompt."""
    from sqlalchemy import func as sa_func
    from sqlalchemy import select

    from app.db.ai_summary_feedback import AISummaryFeedback

    # Overall average rating (ungrouped)
    overall = await db.execute(
        select(
            sa_func.avg(AISummaryFeedback.rating).label("avg_rating"),
            sa_func.count().label("total"),
        ).where(AISummaryFeedback.org_id == org_id)
    )
    overall_row = overall.one()
    total = int(overall_row.total or 0)
    if total < 2:
        return None  # not enough feedback to guide the model

    avg_rating = float(overall_row.avg_rating or 3.0)

    # Top flags by frequency
    flag_result = await db.execute(
        select(
            AISummaryFeedback.flag,
            sa_func.count().label("flag_count"),
        )
        .where(AISummaryFeedback.org_id == org_id)
        .group_by(AISummaryFeedback.flag)
        .order_by(sa_func.count().desc())
        .limit(3)
    )
    flag_rows = flag_result.all()
    top_flags = [r.flag for r in flag_rows[:2]]

    hints: list[str] = []
    if avg_rating < 3.0:
        hints.append("Previous summaries were rated below average.")
    if "too_vague" in top_flags:
        hints.append(
            "Users report summaries are too vague — be more specific about remediation steps and affected systems."
        )
    if "inaccurate" in top_flags:
        hints.append(
            "Users have flagged inaccuracies — double-check claims against the structured findings data."
        )
    if "helpful" in top_flags and avg_rating >= 4.0:
        hints.append(
            "Users find summaries helpful — maintain current level of detail and actionability."
        )

    return " ".join(hints) if hints else None


class AISummaryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _get_cached(self, org_id: int) -> AISummaryResponse | None:
        entry = _cache.get(org_id)
        if entry is None:
            return None
        ts, resp = entry
        if time.time() - ts > settings.AI_SUMMARY_CACHE_TTL:
            del _cache[org_id]
            return None
        return resp

    def _set_cache(self, org_id: int, resp: AISummaryResponse) -> None:
        _cache[org_id] = (time.time(), resp)

    def invalidate(self, org_id: int) -> None:
        """Remove cached summary for the given org (call on profile update)."""
        _cache.pop(org_id, None)

    async def build(
        self,
        org: Organization,
        *,
        triggered_by_user_id: int | None = None,
    ) -> AISummaryResponse:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from app.db.findings_snapshot import FindingsSnapshot
        # Check cache first
        cached = self._get_cached(org.id)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        # Build findings report
        report = await FindingsEngine(self._db).build(org)

        # Link to most recent snapshot if available
        snap_result = await self._db.execute(
            select(FindingsSnapshot.id)
            .where(FindingsSnapshot.org_id == org.id)
            .order_by(FindingsSnapshot.generated_at.desc())
            .limit(1)
        )
        snap_id = snap_result.scalar_one_or_none()

        # Risk score
        risk_resp = calculate_smb_risk_score(org.industry_label, org.employee_range)
        risk_score = risk_resp.score
        risk_label = _risk_label(risk_score)

        generated_at = datetime.now(UTC).isoformat()
        disclaimer = (
            "This summary is generated from automated threat intelligence data and is intended "
            "for informational purposes only. It does not constitute professional security advice."
        )

        ai_generated = False
        model_used: str | None = None
        narrative: str
        prompt_inputs: dict = {}
        rendered_prompt: str | None = None
        status: str
        error_message: str | None = None
        source: str

        started_at = time.time()

        if settings.AI_SUMMARY_ENABLED and settings.GEMINI_API_KEY:
            try:
                feedback_hint = await _get_feedback_meta(self._db, org.id)
                rendered_prompt, prompt_inputs = _build_prompt(
                    org, report, risk_score, feedback_hint=feedback_hint
                )
                narrative = await _call_gemini(rendered_prompt)
                ai_generated = True
                model_used = settings.GEMINI_MODEL
                status = "success"
                source = "gemini"
            except Exception as e:
                logger.exception("Gemini API call failed for org %s — using fallback", org.id)
                error_message = str(e)
                narrative = _build_fallback(org, report, risk_score)
                status = "fallback_used"
                source = "fallback"
                model_used = settings.GEMINI_MODEL
        else:
            narrative = _build_fallback(org, report, risk_score)
            status = "success"
            source = "fallback"
            model_used = "fallback-template"

        latency_ms = int((time.time() - started_at) * 1000)

        try:
            repo = SqlAISummaryGenerationRepository(self._db)
            await repo.create(
                org_id=org.id,
                model_name=model_used or "fallback-template",
                source=source,
                status=status,
                error_message=error_message,
                prompt_inputs=prompt_inputs,
                rendered_prompt=rendered_prompt,
                output_text=narrative,
                findings_snapshot_id=snap_id,
                triggered_by_user_id=triggered_by_user_id,
                latency_ms=latency_ms,
            )
        except Exception:
            logger.exception("Failed to persist AI summary generation row for org %s", org.id)

        disclaimer_block = get_disclaimer(
            DisclaimerContext.AI_SUMMARY,
            tier=report.assessment_tier,
            data_sources=report.data_sources_used,
        )

        resp = AISummaryResponse(
            narrative=narrative,
            ai_generated=ai_generated,
            model_used=model_used,
            findings_count=report.summary.total,
            risk_score=risk_score,
            risk_label=risk_label,
            generated_at=generated_at,
            cached=False,
            disclaimer=disclaimer,
            disclaimer_block=disclaimer_block,
        )

        self._set_cache(org.id, resp)
        return resp
