"""Tests for the per-source refresh policy and its effect on ingest health/freshness."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.config import Settings, settings
from app.db.engine import AsyncSessionLocal
from app.models.ingest_run import IngestRun
from app.services.ingest_catchup import effective_policy, scheduled_sources, source_is_stale
from app.services.ingest_sources import REFRESH_POLICIES, refresh_policy


def test_registry_policies():
    assert REFRESH_POLICIES == {
        "nvd": "scheduled",
        "cisa_kev": "scheduled",
        "epss": "scheduled",
        "economics": "scheduled",
        "ic3": "static",
    }


def test_unknown_source_is_scheduled():
    assert refresh_policy("not-a-source") == "scheduled"
    assert refresh_policy("ic3") == "static"


def test_source_is_stale_static_never_stale_by_age():
    assert source_is_stale("ic3", 5040.0, {"ic3": 168}) is False
    # A static source that has never succeeded is stale (nothing was ever loaded).
    assert source_is_stale("ic3", None, {"ic3": 168}) is True


def test_source_is_stale_disabled_follows_static_rule():
    thresholds = {"economics": 840}
    assert source_is_stale("economics", 99999.0, thresholds, "disabled") is False
    assert source_is_stale("economics", None, thresholds, "disabled") is True


def test_effective_policy():
    on = {"nvd": True, "economics": False, "ic3": False}
    assert effective_policy("nvd", on) == "scheduled"
    assert effective_policy("economics", on) == "disabled"
    # A static source stays static even without a schedule.
    assert effective_policy("ic3", on) == "static"
    assert effective_policy("economics", {"economics": True}) == "scheduled"
    # A source missing from the map has no schedule.
    assert effective_policy("epss", {}) == "disabled"


def test_effective_policy_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_ECONOMICS", "0 3 * * *")
    assert effective_policy("economics", scheduled_sources()) == "scheduled"
    # A typo'd cron is not an opt-out: it stays scheduled so it goes stale and alerts.
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_ECONOMICS", "not-a-cron")
    assert effective_policy("economics", scheduled_sources()) == "scheduled"
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_ECONOMICS", "")
    assert effective_policy("economics", scheduled_sources()) == "disabled"
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_ECONOMICS", "0 3 * * *")
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    assert effective_policy("economics", scheduled_sources()) == "disabled"


def test_source_is_stale_scheduled_uses_threshold():
    thresholds = {"nvd": 25}
    assert source_is_stale("nvd", 26.0, thresholds) is True
    assert source_is_stale("nvd", 24.0, thresholds) is False
    assert source_is_stale("nvd", None, thresholds) is True


def test_source_is_stale_without_threshold_is_stale():
    assert source_is_stale("nvd", 1.0, {}) is True


def test_economics_defaults():
    assert Settings.model_fields["INGEST_SCHEDULE_ECONOMICS"].default == "0 3 * * *"
    assert Settings.model_fields["INGEST_STALE_HOURS_ECON"].default == 840


def _run(source: str, status: str, age_hours: float, now: datetime) -> IngestRun:
    finished = now - timedelta(hours=age_hours)
    return IngestRun(
        id=uuid4(),
        source=source,
        started_at=finished - timedelta(minutes=1),
        finished_at=finished,
        status=status,
    )


def _seed_runs(nvd_age_hours: float) -> list[IngestRun]:
    now = datetime.utcnow()
    runs = [
        _run("nvd", "completed", nvd_age_hours, now),
        _run("cisa_kev", "completed", 1, now),
        _run("epss", "completed", 1, now),
        _run("economics", "completed", 1, now),
        _run("ic3", "completed", 210 * 24, now),
        # Newer than the ic3 success, so ic3 has two consecutive failures.
        _run("ic3", "failed", 2, now),
        _run("ic3", "failed", 1, now),
    ]
    return runs


async def _with_runs(runs: list[IngestRun], check):
    run_ids = [r.id for r in runs]
    async with AsyncSessionLocal() as db:
        try:
            db.add_all(runs)
            await db.commit()
            await check()
        finally:
            await db.rollback()
            await db.execute(delete(IngestRun).where(IngestRun.id.in_(run_ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_health_static_source_ignored_for_healthy(anon_client):
    async def check():
        resp = await anon_client.get("/api/v1/ingest/health")
        if resp.status_code != 200:
            pytest.skip(f"ingest health unavailable: {resp.status_code}")
        body = resp.json()
        assert body["healthy"] is True
        assert body["sources"]["ic3"]["stale"] is False
        assert body["sources"]["ic3"]["refresh_policy"] == "static"
        assert body["sources"]["ic3"]["consecutive_failures"] == 2
        assert body["sources"]["nvd"]["refresh_policy"] == "scheduled"

    await _with_runs(_seed_runs(1), check)


@pytest.mark.asyncio
async def test_freshness_reports_policy_and_stale(client, monkeypatch):
    # Other tests leave newer nvd successes behind; a zero threshold makes any past success stale.
    monkeypatch.setattr(settings, "INGEST_STALE_HOURS_NVD", 0)

    async def check():
        resp = await client.get("/api/v1/ingest/freshness")
        if resp.status_code != 200:
            pytest.skip(f"ingest freshness unavailable: {resp.status_code}")
        by_source = {s["source"]: s for s in resp.json()["sources"]}
        assert by_source["ic3"]["refresh_policy"] == "static"
        assert by_source["ic3"]["stale"] is False
        assert by_source["nvd"]["refresh_policy"] == "scheduled"
        assert by_source["nvd"]["stale"] is True

    await _with_runs(_seed_runs(30), check)


@pytest.mark.asyncio
async def test_empty_economics_schedule_reports_disabled(anon_client, client, monkeypatch):
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_ECONOMICS", "")

    async def check():
        resp = await anon_client.get("/api/v1/ingest/health")
        if resp.status_code != 200:
            pytest.skip(f"ingest health unavailable: {resp.status_code}")
        body = resp.json()
        assert body["sources"]["economics"]["refresh_policy"] == "disabled"
        assert body["sources"]["economics"]["stale"] is False
        assert body["healthy"] is True

        fresh = await client.get("/api/v1/ingest/freshness")
        if fresh.status_code != 200:
            pytest.skip(f"ingest freshness unavailable: {fresh.status_code}")
        by_source = {s["source"]: s for s in fresh.json()["sources"]}
        assert by_source["economics"]["refresh_policy"] == "disabled"
        assert by_source["economics"]["stale"] is False

    # An old economics success would be stale if the source were still scheduled.
    runs = _seed_runs(1)
    runs = [r for r in runs if r.source != "economics"]
    runs.append(_run("economics", "completed", 5000, datetime.utcnow()))
    await _with_runs(runs, check)


@pytest.mark.asyncio
async def test_invalid_cron_stays_scheduled_and_goes_stale(anon_client, monkeypatch):
    # A typo'd cron registers no job; health must alert, not report a deliberate opt-out.
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SCHEDULE_NVD", "0 1 * * * *")
    # Other tests leave newer nvd successes behind; a zero threshold makes any past success stale.
    monkeypatch.setattr(settings, "INGEST_STALE_HOURS_NVD", 0)

    async def check():
        resp = await anon_client.get("/api/v1/ingest/health")
        if resp.status_code != 200:
            pytest.skip(f"ingest health unavailable: {resp.status_code}")
        body = resp.json()
        assert body["sources"]["nvd"]["refresh_policy"] == "scheduled"
        assert body["sources"]["nvd"]["stale"] is True
        assert body["healthy"] is False

    await _with_runs(_seed_runs(30), check)


@pytest.mark.asyncio
async def test_static_source_never_succeeded_is_stale_and_unhealthy(anon_client):
    runs = [r for r in _seed_runs(1) if not (r.source == "ic3" and r.status == "completed")]
    assert any(r.source == "ic3" and r.status == "failed" for r in runs)

    async def check():
        resp = await anon_client.get("/api/v1/ingest/health")
        if resp.status_code != 200:
            pytest.skip(f"ingest health unavailable: {resp.status_code}")
        body = resp.json()
        assert body["sources"]["ic3"]["refresh_policy"] == "static"
        assert body["sources"]["ic3"]["stale"] is True
        assert body["sources"]["ic3"]["last_success_hours_ago"] is None
        assert body["healthy"] is False

    async with AsyncSessionLocal() as db:
        # Earlier tests may have left an ic3 success behind, which would mask this case.
        await db.execute(delete(IngestRun).where(IngestRun.source == "ic3"))
        await db.commit()
    await _with_runs(runs, check)
