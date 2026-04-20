"""Repository abstraction for versioned assessment submissions."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.assessment_submission import AssessmentSubmission
from app.db.engine import get_session
from app.schemas.assessment_submission import (
    AssessmentSubmissionCreate,
    AssessmentSubmissionUpdate,
)


class SqlAssessmentSubmissionRepository:
    """Database access for immutable assessment submissions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_initial(self, payload: AssessmentSubmissionCreate) -> AssessmentSubmission:
        existing_current = await self.get_current_by_org(payload.organization_id)
        if existing_current is not None:
            raise ValueError("Current assessment already exists for organization")

        row = AssessmentSubmission(
            organization_id=payload.organization_id,
            status=payload.status.value,
            data=payload.data.model_dump(),
            version=1,
            is_current=True,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get_by_id(self, assessment_id: str) -> AssessmentSubmission | None:
        result = await self._session.execute(
            select(AssessmentSubmission).where(
                AssessmentSubmission.id == assessment_id,
                AssessmentSubmission.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_current_by_org(self, organization_id: int) -> AssessmentSubmission | None:
        result = await self._session.execute(
            select(AssessmentSubmission).where(
                AssessmentSubmission.organization_id == organization_id,
                AssessmentSubmission.is_current.is_(True),
                AssessmentSubmission.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_history_by_org(self, organization_id: int) -> list[AssessmentSubmission]:
        result = await self._session.execute(
            select(AssessmentSubmission)
            .where(
                AssessmentSubmission.organization_id == organization_id,
                AssessmentSubmission.deleted_at.is_(None),
            )
            .order_by(AssessmentSubmission.version.desc())
        )
        return list(result.scalars().all())

    async def create_new_version(
        self, assessment_id: str, payload: AssessmentSubmissionUpdate
    ) -> AssessmentSubmission:
        async with self._session.begin():
            target_result = await self._session.execute(
                select(AssessmentSubmission)
                .where(
                    AssessmentSubmission.id == assessment_id,
                    AssessmentSubmission.deleted_at.is_(None),
                )
                .with_for_update()
            )
            target = target_result.scalar_one_or_none()
            if target is None:
                raise LookupError("Assessment not found")
            if not target.is_current:
                raise ValueError("Only the current assessment version can be updated")

            current_result = await self._session.execute(
                select(AssessmentSubmission)
                .where(
                    AssessmentSubmission.organization_id == target.organization_id,
                    AssessmentSubmission.is_current.is_(True),
                    AssessmentSubmission.deleted_at.is_(None),
                )
                .with_for_update()
            )
            current = current_result.scalar_one_or_none()
            if current is None:
                raise LookupError("Current assessment not found")
            if current.id != target.id:
                raise ValueError("Provided assessment id is not the latest current version")

            next_version = current.version + 1
            current.is_current = False
            new_row = AssessmentSubmission(
                organization_id=current.organization_id,
                status=payload.status.value,
                data=payload.data.model_dump(),
                version=next_version,
                is_current=True,
            )
            self._session.add(new_row)

        await self._session.refresh(new_row)
        return new_row

    async def soft_delete(self, assessment_id: str) -> AssessmentSubmission | None:
        async with self._session.begin():
            row_result = await self._session.execute(
                select(AssessmentSubmission)
                .where(
                    AssessmentSubmission.id == assessment_id,
                    AssessmentSubmission.deleted_at.is_(None),
                )
                .with_for_update()
            )
            row = row_result.scalar_one_or_none()
            if row is None:
                return None

            row.deleted_at = datetime.now(UTC)
            row.is_current = False

            replacement_result = await self._session.execute(
                select(AssessmentSubmission)
                .where(
                    and_(
                        AssessmentSubmission.organization_id == row.organization_id,
                        AssessmentSubmission.id != row.id,
                        AssessmentSubmission.deleted_at.is_(None),
                    )
                )
                .order_by(AssessmentSubmission.version.desc())
                .limit(1)
                .with_for_update()
            )
            replacement = replacement_result.scalar_one_or_none()
            if replacement is not None:
                replacement.is_current = True

        await self._session.refresh(row)
        return row


def get_assessment_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAssessmentSubmissionRepository:
    """Factory used as a dependency in the API layer."""
    return SqlAssessmentSubmissionRepository(session)
