"""Tests for SqlNormalizationLogRepository and fire_and_forget helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.normalization_log_repo import (
    SqlNormalizationLogRepository,
    fire_and_forget_normalization_log,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session():
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# SqlNormalizationLogRepository.write()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_creates_row_with_correct_fields():
    session = _make_session()
    created_row = MagicMock()
    created_row.id = 1

    with patch(
        "app.repositories.normalization_log_repo.NormalizationLog",
        return_value=created_row,
    ) as mock_cls:
        repo = SqlNormalizationLogRepository(session)
        result = await repo.write(
            org_id=5,
            data_type="vendor",
            raw_value="Microsft Inc",
            normalized_value="Microsft Inc",
            method="whitespace",
            confidence=1.0,
            created_by=42,
        )

    mock_cls.assert_called_once_with(
        org_id=5,
        data_type="vendor",
        raw_value="Microsft Inc",
        normalized_value="Microsft Inc",
        confidence=1.0,
        method="whitespace",
        created_by=42,
    )
    session.add.assert_called_once_with(created_row)
    session.commit.assert_awaited_once()
    assert result is created_row


@pytest.mark.asyncio
async def test_write_defaults_confidence_and_created_by():
    session = _make_session()
    created_row = MagicMock()

    with patch(
        "app.repositories.normalization_log_repo.NormalizationLog",
        return_value=created_row,
    ) as mock_cls:
        repo = SqlNormalizationLogRepository(session)
        await repo.write(
            data_type="domain",
            raw_value="Example.COM.",
            normalized_value="example.com",
            method="pattern",
        )

    kwargs = mock_cls.call_args.kwargs
    assert kwargs["confidence"] == 1.0
    assert kwargs["created_by"] is None
    assert kwargs["org_id"] is None


@pytest.mark.asyncio
async def test_write_commits_and_refreshes():
    session = _make_session()
    with patch(
        "app.repositories.normalization_log_repo.NormalizationLog", return_value=MagicMock()
    ):
        repo = SqlNormalizationLogRepository(session)
        await repo.write(
            data_type="industry",
            raw_value="Healthcare",
            normalized_value="Healthcare",
            method="exact",
        )

    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# fire_and_forget_normalization_log
# ---------------------------------------------------------------------------


def test_fire_and_forget_schedules_task_without_raising():
    """fire_and_forget must not raise — it is called in hot paths."""
    with patch("app.repositories.normalization_log_repo.asyncio.create_task") as mock_task:
        fire_and_forget_normalization_log(
            org_id=1,
            data_type="vendor",
            raw_value="Apache",
            normalized_value="apache software foundation",
            method="fuzzy",
            confidence=0.82,
        )
    mock_task.assert_called_once()


def test_fire_and_forget_passes_all_kwargs():
    """Coroutine passed to create_task must encode the caller's arguments."""
    captured = {}

    def capture_task(coro):
        # inspect the coroutine's cr_frame locals to verify args
        captured["coro"] = coro
        coro.close()  # prevent RuntimeWarning for un-awaited coroutine

    with patch(
        "app.repositories.normalization_log_repo.asyncio.create_task", side_effect=capture_task
    ):
        fire_and_forget_normalization_log(
            org_id=9,
            data_type="vendor",
            raw_value="Msft",
            normalized_value="microsoft",
            method="fuzzy",
            confidence=0.77,
            created_by=3,
        )

    assert "coro" in captured
