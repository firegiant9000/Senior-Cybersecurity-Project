"""Repository tests for the anonymous readiness funnel counters.

Requires the test Postgres. Only this feature touches ``readiness_funnel_counts``,
so each test wipes the table before and after.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest_asyncio
from sqlalchemy import delete

from app.db.engine import AsyncSessionLocal
from app.db.readiness_funnel_count import ReadinessFunnelCount
from app.repositories.readiness_funnel import (
    FunnelCountRow,
    SqlReadinessFunnelRepository,
)

DAY = date(2026, 1, 1)


async def _wipe() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ReadinessFunnelCount))
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean_table():
    await _wipe()
    yield
    await _wipe()


async def _increment(day: date, version: str, step: str) -> None:
    async with AsyncSessionLocal() as session:
        await SqlReadinessFunnelRepository(session).increment(day, version, step)
        await session.commit()


async def _counts(start: date, end: date) -> list[FunnelCountRow]:
    async with AsyncSessionLocal() as session:
        return await SqlReadinessFunnelRepository(session).counts_between(start, end)


async def test_first_increment_creates_row():
    await _increment(DAY, "v1", "quiz_started")
    assert await _counts(DAY, DAY) == [FunnelCountRow(DAY, "v1", "quiz_started", 1)]


async def test_second_increment_updates_row():
    await _increment(DAY, "v1", "quiz_started")
    await _increment(DAY, "v1", "quiz_started")
    assert await _counts(DAY, DAY) == [FunnelCountRow(DAY, "v1", "quiz_started", 2)]


async def test_distinct_keys_are_distinct_rows():
    await _increment(DAY, "v1", "quiz_started")
    await _increment(DAY, "v1", "quiz_completed")
    await _increment(DAY, "v2", "quiz_started")
    await _increment(DAY + timedelta(days=1), "v1", "quiz_started")
    rows = await _counts(DAY, DAY + timedelta(days=1))
    assert len(rows) == 4
    assert all(r.count == 1 for r in rows)


async def test_concurrent_increments_leave_one_row():
    await asyncio.gather(*(_increment(DAY, "v1", "quiz_started") for _ in range(20)))
    assert await _counts(DAY, DAY) == [FunnelCountRow(DAY, "v1", "quiz_started", 20)]


async def test_counts_between_is_inclusive_and_ordered():
    d = DAY
    await _increment(d - timedelta(days=1), "v1", "a")
    await _increment(d + timedelta(days=1), "v1", "b")
    await _increment(d + timedelta(days=1), "v1", "a")
    await _increment(d, "v1", "z")
    await _increment(d + timedelta(days=2), "v1", "a")
    rows = await _counts(d, d + timedelta(days=1))
    assert [(r.day, r.step) for r in rows] == [
        (d, "z"),
        (d + timedelta(days=1), "a"),
        (d + timedelta(days=1), "b"),
    ]
