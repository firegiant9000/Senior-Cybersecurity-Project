"""Tests for scheduler job registration logic."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings, settings
from app.workers.scheduler import _catchup_sweep, init_scheduler, source_cron_exprs

_FIELD = {
    "nvd": "INGEST_SCHEDULE_NVD",
    "cisa_kev": "INGEST_SCHEDULE_KEV",
    "ic3": "INGEST_SCHEDULE_IC3",
    "economics": "INGEST_SCHEDULE_ECONOMICS",
    "epss": "INGEST_SCHEDULE_EPSS",
}


def _default_map() -> dict[str, str]:
    # Code defaults, independent of any env override on the test machine.
    return {source: Settings.model_fields[field].default for source, field in _FIELD.items()}


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
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
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
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = ""
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_invalid_cron_skipped(mock_scheduler):
    source_map = {"nvd": "not-a-cron", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = ""
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_matcher_sweep_job_registered(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = "30 2 * * *"
        init_scheduler()

    job_ids = {call.kwargs["id"] for call in mock_scheduler.add_job.call_args_list}
    assert job_ids == {"matcher_sweep"}


def test_matcher_sweep_invalid_cron_skipped(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = "not-a-cron"
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_retention_sweep_job_registered(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = ""
        mock_settings.NVD_CPE_BACKFILL_SCHEDULE = ""
        mock_settings.RETENTION_SWEEP_SCHEDULE = "0 5 * * *"
        init_scheduler()

    job_ids = {call.kwargs["id"] for call in mock_scheduler.add_job.call_args_list}
    assert "retention_sweep" in job_ids


def test_retention_sweep_invalid_cron_skipped(mock_scheduler):
    source_map = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=source_map),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = ""
        mock_settings.NVD_CPE_BACKFILL_SCHEDULE = ""
        mock_settings.RETENTION_SWEEP_SCHEDULE = "not-a-cron"
        init_scheduler()
    mock_scheduler.add_job.assert_not_called()


def test_production_defaults_register_nvd_kev_epss_in_order(mock_scheduler):
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=_default_map()),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = ""
        mock_settings.NVD_CPE_BACKFILL_SCHEDULE = ""
        mock_settings.RETENTION_SWEEP_SCHEDULE = ""
        init_scheduler()

    triggers = {c.kwargs["id"]: c.kwargs["trigger"] for c in mock_scheduler.add_job.call_args_list}
    assert set(triggers) == {"ingest_nvd", "ingest_cisa_kev", "ingest_epss"}
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    fire = {k: v.get_next_fire_time(None, t0) for k, v in triggers.items()}
    assert fire["ingest_nvd"] < fire["ingest_cisa_kev"] < fire["ingest_epss"]
    assert (fire["ingest_nvd"].hour, fire["ingest_nvd"].minute) == (1, 0)


def _catchup_jobs(mock_scheduler, *, schedule, on_startup=True):
    empty = {"nvd": "", "cisa_kev": "", "ic3": "", "economics": "", "epss": ""}
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=empty),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.MATCHER_SCHEDULE = ""
        mock_settings.NVD_CPE_BACKFILL_SCHEDULE = ""
        mock_settings.RETENTION_SWEEP_SCHEDULE = ""
        mock_settings.INGEST_CATCHUP_SCHEDULE = schedule
        mock_settings.INGEST_CATCHUP_ON_STARTUP = on_startup
        init_scheduler()
    return {c.kwargs["id"]: c.kwargs for c in mock_scheduler.add_job.call_args_list}


def test_catchup_sweep_registered_with_default_cron(mock_scheduler):
    default = Settings.model_fields["INGEST_CATCHUP_SCHEDULE"].default
    assert default == "45 * * * *"
    jobs = _catchup_jobs(mock_scheduler, schedule=default)

    assert set(jobs) == {"catchup_sweep"}
    job = jobs["catchup_sweep"]
    assert job["misfire_grace_time"] == 300
    assert job["coalesce"] is True
    assert job["max_instances"] == 1
    assert job["replace_existing"] is True
    fire = job["trigger"].get_next_fire_time(None, datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    assert (fire.hour, fire.minute) == (0, 45)


def test_catchup_sweep_not_registered_when_schedule_empty(mock_scheduler):
    assert _catchup_jobs(mock_scheduler, schedule="") == {}


def test_catchup_sweep_not_registered_when_catchup_disabled(mock_scheduler):
    assert _catchup_jobs(mock_scheduler, schedule="45 * * * *", on_startup=False) == {}


def test_catchup_sweep_invalid_cron_skipped(mock_scheduler):
    assert _catchup_jobs(mock_scheduler, schedule="not-a-cron") == {}


async def test_catchup_sweep_job_runs_catchup_with_catchup_trigger():
    with patch("app.services.ingest_catchup.run_catchup", new=AsyncMock()) as run:
        await _catchup_sweep()
    run.assert_awaited_once_with("catchup")


async def test_catchup_sweep_job_swallows_errors():
    with patch("app.services.ingest_catchup.run_catchup", new=AsyncMock(side_effect=OSError("db"))):
        await _catchup_sweep()


def test_source_cron_exprs_reads_settings_at_call_time(monkeypatch):
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_NVD", "5 4 * * *")
    assert source_cron_exprs()["nvd"] == "5 4 * * *"
    assert set(source_cron_exprs()) == set(_FIELD)


def test_ingest_jobs_have_one_hour_misfire_grace(mock_scheduler):
    with (
        patch("app.workers.scheduler.settings") as mock_settings,
        patch("app.workers.scheduler.source_cron_exprs", return_value=_default_map()),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGEST_CATCHUP_SCHEDULE = ""
        mock_settings.MATCHER_SCHEDULE = "30 2 * * *"
        mock_settings.NVD_CPE_BACKFILL_SCHEDULE = "0 4 * * *"
        mock_settings.RETENTION_SWEEP_SCHEDULE = "0 5 * * *"
        init_scheduler()

    grace = {
        c.kwargs["id"]: c.kwargs["misfire_grace_time"]
        for c in mock_scheduler.add_job.call_args_list
    }
    assert all(grace[j] == 3600 for j in grace if j.startswith("ingest_"))
    assert grace["matcher_sweep"] == grace["cpe_backfill"] == grace["retention_sweep"] == 300
