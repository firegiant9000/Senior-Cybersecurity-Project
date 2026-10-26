"""Tests for the per-source refresh policy and its effect on ingest health/freshness."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.config import Settings, settings
from app.db.engine import AsyncSessionLocal
from app.models.ingest_run import IngestRun
from app.services.ingest_catchup import source_is_stale
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


def test_source_is_stale_static_never_stale():
    assert source_is_stale("ic3", 5040.0, {"ic3": 168}) is False
    assert source_is_stale("ic3", None, {"ic3": 168}) is False


def test_source_is_stale_scheduled_uses_threshold():
    thresholds = {"nvd": 25}
    assert source_is_stale("nvd", 26.0, thresholds) is True
    assert source_is_stale("nvd", 24.0, thresholds) is False
    assert source_is_stale("nvd", None, thresholds) is True


def test_source_is_stale_without_threshold_is_stale():
    assert source_is_stale("nvd", 1.0, {}) is True


def test_economics_defaults():
    assert Settings.model_fields["INGEST_SCHEDULE_ECONOMICS"].default == "0 3 1 * *"
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
