"""Tests for backend/app/services/loss_projection.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.loss_projection import LossProjectionService, _fmt_loss

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org(
    *,
    ic3_sector: str = "Healthcare",
    primary_state: str = "CA",
    employee_range: str = "11-50",
    org_id: int = 1,
) -> MagicMock:
    m = MagicMock()
    m.id = org_id
    m.ic3_sector = ic3_sector
    m.primary_state = primary_state
    m.employee_range = employee_range
    return m


def _db_returning(rows_by_call: list[list[tuple]]) -> AsyncMock:
    """Create a mock AsyncSession whose .execute() returns canned rows.

    rows_by_call is a list of call results. Each call result is a list of
    tuples.  Odd calls are year lookups (return .all()), even calls are
    aggregations (return .one()).
    """
    db = AsyncMock()
    results = []
    for rows in rows_by_call:
        result = MagicMock()
        result.all.return_value = rows
        result.one.return_value = rows[0] if rows else (None, None, None, None)
        results.append(result)
    db.execute = AsyncMock(side_effect=results)
    return db


# ---------------------------------------------------------------------------
# _fmt_loss
# ---------------------------------------------------------------------------


class TestFmtLoss:
    def test_zero(self):
        assert _fmt_loss(0) == "$0"

    def test_small(self):
        assert _fmt_loss(999) == "$999"

    def test_thousands(self):
        assert _fmt_loss(1_000) == "$1k"
        assert _fmt_loss(5_500) == "$6k"

    def test_millions(self):
        assert _fmt_loss(1_000_000) == "$1.0M"
        assert _fmt_loss(1_200_000) == "$1.2M"

    def test_billions(self):
        assert _fmt_loss(1_000_000_000) == "$1.0B"
        assert _fmt_loss(2_500_000_000) == "$2.5B"


# ---------------------------------------------------------------------------
# LossProjectionService.build — fallback chain
# ---------------------------------------------------------------------------


class TestLossProjectionBuild:
    @pytest.mark.asyncio
    async def test_sector_and_state_match_high_confidence(self):
        """When sector+state data exists, confidence is High."""
        db = _db_returning([
            # Year lookup: sector+state → 2 years found
            [(2023,), (2022,)],
            # Aggregation: avg_loss=50000, complaints=200, year range 2022-2023
            [(50_000.0, 200, 2022, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(employee_range="11-50"))

        assert result.has_data is True
        assert result.confidence_level == "High"
        assert result.projected_annual_loss == pytest.approx(50_000.0 * 0.8)
        assert result.ic3_avg_loss_per_incident == pytest.approx(50_000.0)
        assert result.ic3_incident_count == 200
        assert result.ic3_data_years == "2022–2023"

    @pytest.mark.asyncio
    async def test_falls_back_to_sector_only_medium_confidence(self):
        """When sector+state has no data, falls back to sector-only."""
        db = _db_returning([
            # Year lookup: sector+state → empty
            [],
            # Year lookup: sector-only → 1 year
            [(2023,)],
            # Aggregation: sector-only
            [(30_000.0, 100, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org())

        assert result.has_data is True
        assert result.confidence_level == "Medium"
        assert result.ic3_data_years == "2023"

    @pytest.mark.asyncio
    async def test_falls_back_to_national_low_confidence(self):
        """When both sector+state and sector-only have no data, falls back to national."""
        db = _db_returning([
            # Year lookup: sector+state → empty
            [],
            # Year lookup: sector-only → empty
            [],
            # Year lookup: national → 3 years
            [(2023,), (2022,), (2021,)],
            # Aggregation: national
            [(20_000.0, 5000, 2021, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org())

        assert result.has_data is True
        assert result.confidence_level == "Low"

    @pytest.mark.asyncio
    async def test_no_data_at_all(self):
        """When no IC3 data exists at all, has_data is False."""
        db = _db_returning([
            [],  # sector+state years
            [],  # sector-only years
            [],  # national years
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org())

        assert result.has_data is False
        assert result.projected_annual_loss == 0.0
        assert result.projected_annual_loss_formatted == "$0"
        assert result.ic3_avg_loss_per_incident is None
        assert result.ic3_incident_count is None


# ---------------------------------------------------------------------------
# Employee-range scaling
# ---------------------------------------------------------------------------


class TestEmployeeRangeScaling:
    @pytest.mark.asyncio
    async def test_solo_scales_by_0_3(self):
        db = _db_returning([
            [(2023,)],
            [(100_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(employee_range="1-10"))

        assert result.size_multiplier == pytest.approx(0.3)
        assert result.projected_annual_loss == pytest.approx(100_000.0 * 0.3)

    @pytest.mark.asyncio
    async def test_large_enterprise_scales_by_9(self):
        db = _db_returning([
            [(2023,)],
            [(100_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(employee_range="1001+"))

        assert result.size_multiplier == pytest.approx(9.0)
        assert result.projected_annual_loss == pytest.approx(100_000.0 * 9.0)

    @pytest.mark.asyncio
    async def test_unknown_range_defaults_to_1(self):
        db = _db_returning([
            [(2023,)],
            [(100_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(employee_range="unknown"))

        assert result.size_multiplier == pytest.approx(1.0)
        assert result.projected_annual_loss == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# Empty-string normalisation
# ---------------------------------------------------------------------------


class TestEmptyStringNormalisation:
    @pytest.mark.asyncio
    async def test_empty_sector_skips_to_national(self):
        """Empty ic3_sector should behave like None, skipping sector queries."""
        db = _db_returning([
            # sector+state with sector="" → no years (normalised to None)
            [],
            # sector-only with sector="" → no years (normalised to None)
            [],
            # national → data found
            [(2023,)],
            [(10_000.0, 100, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(ic3_sector="", primary_state="CA"))

        assert result.has_data is True
        assert result.confidence_level == "Low"

    @pytest.mark.asyncio
    async def test_empty_state_skips_state_filter(self):
        """Empty primary_state should be treated as None."""
        db = _db_returning([
            # sector+state with state="" → treated as sector+None
            [(2023,)],
            [(25_000.0, 80, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(ic3_sector="Finance", primary_state=""))

        assert result.has_data is True


# ---------------------------------------------------------------------------
# Response metadata
# ---------------------------------------------------------------------------


class TestResponseMetadata:
    @pytest.mark.asyncio
    async def test_sector_and_state_echoed(self):
        db = _db_returning([
            [(2023,)],
            [(10_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org(ic3_sector="Tech", primary_state="NY"))

        assert result.sector == "Tech"
        assert result.state == "NY"
        assert result.employee_range == "11-50"

    @pytest.mark.asyncio
    async def test_methodology_is_populated(self):
        db = _db_returning([
            [(2023,)],
            [(10_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org())

        assert "complaint-weighted" in result.methodology
        assert result.generated_at  # non-empty ISO string

    @pytest.mark.asyncio
    async def test_single_year_range(self):
        """When only one year of data, year range should be just that year."""
        db = _db_returning([
            [(2023,)],
            [(10_000.0, 50, 2023, 2023)],
        ])
        svc = LossProjectionService(db)
        result = await svc.build(_org())

        assert result.ic3_data_years == "2023"
