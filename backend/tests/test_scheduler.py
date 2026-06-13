"""Tests for scheduler job registration logic."""

from unittest.mock import patch

import pytest

from app.workers.scheduler import init_scheduler


@pytest.fixture()
def mock_scheduler():
    with patch("app.workers.scheduler.scheduler") as sched:
        yield sched


def test_no_jobs_when_disabled(mock_scheduler):
    with patch("app.workers.scheduler.settings") as mock_settings:
        mock_settings.SCHEDULER_ENABLED = False
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_jobs_added_when_enabled(mock_scheduler):
    source_map = {
        "nvd": "0 2 * * *",
        "cisa_kev": "0 3 * * *",
        "ic3": "",
        "economics": "",
    }
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler._SOURCE_SCHEDULE_MAP", source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = ""
        init_scheduler()

    assert mock_scheduler.add_job.call_count == 2
    job_ids = {call.kwargs["id"] for call in mock_scheduler.add_job.call_args_list}
    assert "ingest_nvd" in job_ids
    assert "ingest_cisa_kev" in job_ids


def test_empty_cron_skipped(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler._SOURCE_SCHEDULE_MAP", source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = ""
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_invalid_cron_skipped(mock_scheduler):
    source_map = {"nvd": "not-a-cron", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler._SOURCE_SCHEDULE_MAP", source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = ""
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_matcher_sweep_job_registered(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler._SOURCE_SCHEDULE_MAP", source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = "30 2 * * *"
        init_scheduler()

    job_ids = {call.kwargs["id"] for call in mock_scheduler.add_job.call_args_list}
    assert job_ids == {"matcher_sweep"}


def test_matcher_sweep_invalid_cron_skipped(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler._SOURCE_SCHEDULE_MAP", source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = "not-a-cron"
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()
