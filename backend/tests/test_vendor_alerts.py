"""Tests for VendorAlertService — exact match, fuzzy match, confidence scores."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import ProgrammingError

from app.services.vendor_alerts import VendorAlertService

# ---------------------------------------------------------------------------
# Session and row factories
# ---------------------------------------------------------------------------


def _mock_session():
    s = MagicMock()
    s.execute = AsyncMock()
    return s


def _count_result(n: int):
    r = MagicMock()
    r.scalar_one.return_value = n
    return r


def _rows_result(rows: list):
    r = MagicMock()
    r.all.return_value = rows
    return r


def _scalar_or_none_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exact_row(vendor_name="Microsoft", cve_id="CVE-2024-1234", cvss=9.8, severity="Critical"):
    row = MagicMock()
    row.vendor_name = vendor_name
    row.org_product = ""
    row.cve_id = cve_id
    row.kev_product = "Windows"
    row.due_date = None
    row.description = "Test vuln"
    row.cvss_score = cvss
    row.severity = severity
    row.published_date = None
    return row


def _fuzzy_row(
    vendor_name="Microsft",
    kev_vendor="microsoft",
    cve_id="CVE-2024-5678",
    score=0.82,
    cvss=7.5,
    severity="High",
):
    row = MagicMock()
    row.vendor_name = vendor_name
    row.kev_vendor = kev_vendor
    row.org_product = ""
    row.cve_id = cve_id
    row.kev_product = "Windows"
    row.due_date = None
    row.description = "Fuzzy vuln"
    row.cvss_score = cvss
    row.severity = severity
    row.published_date = None
    row.score = score
    return row


# ---------------------------------------------------------------------------
# No vendors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_vendors_returns_early_with_reason():
    session = _mock_session()
    session.execute = AsyncMock(return_value=_count_result(0))

    svc = VendorAlertService(session)
    with patch.object(svc, "_last_kev_ingest", new=AsyncMock(return_value=None)):
        result = await svc.get_alerts(org_id=1)

    assert result.total_matched == 0
    assert result.reason == "no_vendors"
    assert result.items == []


# ---------------------------------------------------------------------------
# Exact match — confidence = 1.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_match_items_have_confidence_1():
    session = _mock_session()
    exact = _exact_row()

    calls = [
        _count_result(1),  # vendor count
        _rows_result([exact]),  # exact match pass
        _rows_result([("Microsoft",)]),  # all vendor names
        # no fuzzy pass because all vendors matched exactly
        _rows_result([]),  # _fetch_other_alerts — no trending KEVs
        _scalar_or_none_result(None),  # last kev ingest
    ]
    session.execute = AsyncMock(side_effect=calls)

    svc = VendorAlertService(session)
    result = await svc.get_alerts(org_id=1)

    assert result.total_matched == 1
    assert len(result.items) == 1
    assert result.items[0].match_confidence == 1.0


# ---------------------------------------------------------------------------
# Fuzzy match — confidence from similarity score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_match_items_carry_similarity_score():
    session = _mock_session()
    fuzzy = _fuzzy_row(score=0.82)

    calls = [
        _count_result(1),  # vendor count
        _rows_result([]),  # exact pass — no matches
        _rows_result([("Microsft",)]),  # all vendor names
        _rows_result([fuzzy]),  # fuzzy pass
        _rows_result([]),  # _fetch_other_alerts — no trending KEVs
        _scalar_or_none_result(None),  # last kev ingest
    ]
    session.execute = AsyncMock(side_effect=calls)

    with patch("app.services.vendor_alerts.fire_and_forget_normalization_log"):
        svc = VendorAlertService(session)
        result = await svc.get_alerts(org_id=1)

    assert result.total_matched == 1
    assert len(result.items) == 1
    assert result.items[0].match_confidence == pytest.approx(0.82)


# ---------------------------------------------------------------------------
# No match — unmatched vendors listed, no items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_match_returns_empty_items_and_unmatched_list():
    session = _mock_session()

    calls = [
        _count_result(1),  # vendor count
        _rows_result([]),  # exact pass — none
        _rows_result([("UnknownVendor",)]),  # all vendor names
        _rows_result([]),  # fuzzy pass — none
        _rows_result([]),  # _fetch_other_alerts (no_matches branch)
        _scalar_or_none_result(None),  # last kev ingest
    ]
    session.execute = AsyncMock(side_effect=calls)

    with patch("app.services.vendor_alerts.fire_and_forget_normalization_log"):
        svc = VendorAlertService(session)
        result = await svc.get_alerts(org_id=1)

    assert result.total_matched == 0
    assert result.items == []
    assert "UnknownVendor" in result.unmatched_vendors
    assert result.reason == "no_matches"


# ---------------------------------------------------------------------------
# Fuzzy match logs to normalization_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_match_calls_fire_and_forget_log():
    session = _mock_session()
    fuzzy = _fuzzy_row(vendor_name="Apche", kev_vendor="apache", score=0.79)

    calls = [
        _count_result(1),
        _rows_result([]),
        _rows_result([("Apche",)]),
        _rows_result([fuzzy]),
        _rows_result([]),  # _fetch_other_alerts
        _scalar_or_none_result(None),
    ]
    session.execute = AsyncMock(side_effect=calls)

    with patch("app.services.vendor_alerts.fire_and_forget_normalization_log") as mock_log:
        svc = VendorAlertService(session)
        await svc.get_alerts(org_id=7)

    mock_log.assert_called_once_with(
        org_id=7,
        data_type="vendor",
        raw_value="Apche",
        normalized_value="apache",
        method="fuzzy",
        confidence=pytest.approx(0.79),
    )


# ---------------------------------------------------------------------------
# Mixed exact + fuzzy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_and_fuzzy_combined_total():
    session = _mock_session()
    exact = _exact_row(vendor_name="Microsoft", cvss=9.8)
    fuzzy = _fuzzy_row(vendor_name="Apche", score=0.80, cvss=7.5)

    calls = [
        _count_result(2),
        _rows_result([exact]),  # Microsoft matched exactly
        _rows_result([("Microsoft",), ("Apche",)]),  # all vendors
        _rows_result([fuzzy]),  # Apche matched by fuzzy
        _rows_result([]),  # _fetch_other_alerts
        _scalar_or_none_result(None),
    ]
    session.execute = AsyncMock(side_effect=calls)

    with patch("app.services.vendor_alerts.fire_and_forget_normalization_log"):
        svc = VendorAlertService(session)
        result = await svc.get_alerts(org_id=1)

    assert result.total_matched == 2
    confidences = {item.match_confidence for item in result.items}
    assert 1.0 in confidences
    assert any(c < 1.0 for c in confidences)


# ---------------------------------------------------------------------------
# Graceful degradation — pg_trgm unavailable (ProgrammingError on fuzzy)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_pg_trgm_unavailable_degrades_to_exact_only():
    """When the fuzzy query raises ProgrammingError (e.g. pg_trgm/`%` missing),
    the service must roll back the poisoned session, skip fuzzy, and still
    return the exact matches plus a successful _last_kev_ingest call."""
    session = _mock_session()
    session.rollback = AsyncMock()
    exact = _exact_row(vendor_name="Microsoft", cvss=9.8)

    fuzzy_err = ProgrammingError(
        statement="SELECT ... similarity(...)",
        params={},
        orig=Exception("function similarity(text, text) does not exist"),
    )

    # Order: vendor count → exact pass → all vendor names → fuzzy (raises)
    # → _fetch_other_alerts → last kev ingest
    call_results = [
        _count_result(2),
        _rows_result([exact]),
        _rows_result([("Microsoft",), ("Apche",)]),  # Apche not in aliases → goes to fuzzy
        fuzzy_err,
        _rows_result([]),  # _fetch_other_alerts
        _scalar_or_none_result(None),
    ]

    async def execute_side_effect(*_args, **_kwargs):
        nxt = call_results.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("app.services.vendor_alerts.fire_and_forget_normalization_log"):
        svc = VendorAlertService(session)
        result = await svc.get_alerts(org_id=1)

    # Rollback ran exactly once — proves the poisoned-session recovery path.
    session.rollback.assert_awaited_once()
    # Exact match still present, fuzzy skipped, no 500 raised.
    assert result.total_matched == 1
    assert len(result.items) == 1
    assert result.items[0].match_confidence == 1.0
    assert "Apche" in result.unmatched_vendors
