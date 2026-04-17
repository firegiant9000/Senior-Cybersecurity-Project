"""Service that composes existing assessment services into a single debug snapshot."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import Organization
from app.schemas.assessment_debug import (
    DebugAssessmentResponse,
    FindingsReadinessBlock,
    RawOrgProfile,
)
from app.services.assessment_intake import evaluate_intake
from app.services.assessment_validator import build_response, run_validation
from app.services.findings_engine import FindingsEngine

logger = logging.getLogger(__name__)

_BLOCKED_TIERS = ("incomplete", "basic")


async def build_assessment_debug_snapshot(
    org: Organization,
    db: AsyncSession,
) -> DebugAssessmentResponse:
    intake, validation_result = await asyncio.gather(
        evaluate_intake(org, db),
        run_validation(org, db),
    )
    validation = build_response(validation_result)
    findings_readiness = await _build_findings_readiness(org, db, intake.current_tier)
    raw_profile = RawOrgProfile.model_validate(org)

    return DebugAssessmentResponse(
        generated_at=datetime.now(UTC),
        org_id=org.id,
        raw_profile=raw_profile,
        intake=intake,
        validation=validation,
        findings_readiness=findings_readiness,
    )


async def _build_findings_readiness(
    org: Organization,
    db: AsyncSession,
    current_tier: str,
) -> FindingsReadinessBlock:
    if current_tier in _BLOCKED_TIERS:
        return FindingsReadinessBlock(
            ready=False,
            current_tier=current_tier,
            blocking_reason=(
                "Organization profile needs at least Enhanced tier "
                "(add vendors, domains, and security controls) before findings are available."
            ),
        )
    try:
        report = await FindingsEngine(db).build(org, persist=False)
        return FindingsReadinessBlock(ready=True, current_tier=current_tier, report=report)
    except Exception:
        logger.exception("Findings engine failed during debug snapshot for org %s", org.id)
        return FindingsReadinessBlock(
            ready=False,
            current_tier=current_tier,
            blocking_reason="Findings engine error — check server logs.",
        )
