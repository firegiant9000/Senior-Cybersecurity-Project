"""Phase 2 (Month 3) — CPE matcher unit tests.

Covers the defensive version comparator, range evaluation, the four confidence
tiers, and the DB-backed pipeline (against a mocked session) so the matcher's
version-aware logic is locked in before the Phase 5 regression harness plugs in.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.cpe_matcher import (
    CpeMatch,
    CpeMatcher,
    assign_confidence,
    compare_versions,
    evaluate_criterion,
    normalize_cpe_token,
    parse_version,
    version_in_range,
)

# ---------------------------------------------------------------------------
# Version parsing + comparison
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("1.2.3", "1.2.3", 0),
        ("1.2", "1.2.0", 0),  # zero-padding
        ("124.0.0", "124.0.1", -1),
        ("20.11.1", "20.2.0", 1),  # numeric, not lexical, ordering
        ("2.15.0", "2.9.0", 1),
        ("v2.3", "2.3", 0),  # leading v stripped
        ("1:1.0", "2.0", 1),  # epoch dominates
        ("1.0.0-rc1", "1.0.0", -1),  # pre-release < final
        ("1.0.0-alpha", "1.0.0-beta", -1),
        ("1.0.0-rc1", "1.0.0-rc2", -1),
        ("1.0.1", "1.0.1f", -1),  # OpenSSL trailing release letter
        ("1.0.1a", "1.0.1f", -1),
    ],
)
def test_compare_versions_known_orderings(a: str, b: str, expected: int) -> None:
    assert compare_versions(a, b) == expected
    # Antisymmetry sanity check.
    assert compare_versions(b, a) == -expected


@pytest.mark.parametrize("bad", ["", None, "not.a.version", "1.0.1rc1", "latest", "2024-Q1"])
def test_compare_versions_returns_none_on_unparseable(bad: str | None) -> None:
    assert compare_versions(bad, "1.0.0") is None
    assert compare_versions("1.0.0", bad) is None


def test_parse_version_handles_build_metadata() -> None:
    assert parse_version("1.2.3+build5") == parse_version("1.2.3")


# ---------------------------------------------------------------------------
# Range evaluation
# ---------------------------------------------------------------------------


def test_version_in_range_inclusive_start_exclusive_end() -> None:
    # Log4j: >= 2.0, < 2.15.0
    assert version_in_range("2.14.1", start_including="2.0", end_excluding="2.15.0") is True
    assert version_in_range("2.0", start_including="2.0", end_excluding="2.15.0") is True
    assert version_in_range("2.15.0", start_including="2.0", end_excluding="2.15.0") is False
    assert version_in_range("1.9", start_including="2.0", end_excluding="2.15.0") is False


def test_version_in_range_wildcard_bounds_ignored() -> None:
    assert version_in_range("5.0", start_including="*", end_excluding="-") is True


def test_version_in_range_unparseable_is_none() -> None:
    assert version_in_range("garbage", start_including="2.0") is None


# ---------------------------------------------------------------------------
# Criterion evaluation
# ---------------------------------------------------------------------------


def test_evaluate_criterion_version_agnostic_is_true() -> None:
    # cpe with '*' version and no bounds → all versions affected.
    assert evaluate_criterion("99.9", cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*") is True


def test_evaluate_criterion_range_match() -> None:
    verdict = evaluate_criterion(
        "2.14.1",
        cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
        start_including="2.0",
        end_excluding="2.15.0",
    )
    assert verdict is True


def test_evaluate_criterion_concrete_version_equality() -> None:
    cpe = "cpe:2.3:a:openssl:openssl:1.0.1:*:*:*:*:*:*:*"
    assert evaluate_criterion("1.0.1", cpe_uri=cpe) is True
    assert evaluate_criterion("1.0.2", cpe_uri=cpe) is False


def test_evaluate_criterion_missing_version_is_none_when_decision_needed() -> None:
    verdict = evaluate_criterion(
        None,
        cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
        start_including="2.0",
        end_excluding="2.15.0",
    )
    assert verdict is None


# ---------------------------------------------------------------------------
# Confidence assignment — one per tier
# ---------------------------------------------------------------------------


def test_confidence_high_on_exact_cpe_uri() -> None:
    cpe = "cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*"
    assert (
        assign_confidence(
            verdict=True,
            asset_version="2.14.1",
            asset_cpe_uri=cpe,
            criterion_cpe_uri=cpe,
            has_range=False,
            cpe_version_concrete=True,
        )
        == "high"
    )


def test_confidence_high_on_concrete_version_equality() -> None:
    assert (
        assign_confidence(
            verdict=True,
            asset_version="1.0.1",
            asset_cpe_uri=None,
            criterion_cpe_uri="cpe:2.3:a:openssl:openssl:1.0.1:*:*:*:*:*:*:*",
            has_range=False,
            cpe_version_concrete=True,
        )
        == "high"
    )


def test_confidence_medium_on_version_in_range() -> None:
    assert (
        assign_confidence(
            verdict=True,
            asset_version="2.14.1",
            asset_cpe_uri=None,
            criterion_cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
            has_range=True,
            cpe_version_concrete=False,
        )
        == "medium"
    )


def test_confidence_low_on_name_only_match() -> None:
    assert (
        assign_confidence(
            verdict=True,
            asset_version=None,
            asset_cpe_uri=None,
            criterion_cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
            has_range=False,
            cpe_version_concrete=False,
        )
        == "low"
    )


def test_confidence_needs_review_on_unknown_verdict() -> None:
    assert (
        assign_confidence(
            verdict=None,
            asset_version="weird-version",
            asset_cpe_uri=None,
            criterion_cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
            has_range=True,
            cpe_version_concrete=False,
        )
        == "needs_review"
    )


def test_confidence_none_when_not_affected() -> None:
    assert (
        assign_confidence(
            verdict=False,
            asset_version="3.0.0",
            asset_cpe_uri=None,
            criterion_cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
            has_range=True,
            cpe_version_concrete=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Apache Software", "apache_software"),
        ("  Log4j  ", "log4j"),
        ("Red-Hat", "red_hat"),
        ("OpenSSL", "openssl"),
        ("", ""),
    ],
)
def test_normalize_cpe_token(raw: str, expected: str) -> None:
    assert normalize_cpe_token(raw) == expected


# ---------------------------------------------------------------------------
# DB-backed pipeline (mocked session)
# ---------------------------------------------------------------------------


def _criterion_row(**kwargs: object) -> MagicMock:
    row = MagicMock()
    row.cve_id = kwargs.get("cve_id", "CVE-2021-44228")
    row.cpe_uri = kwargs.get("cpe_uri", "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*")
    row.vendor = kwargs.get("vendor", "apache")
    row.product = kwargs.get("product", "log4j")
    row.version_start_including = kwargs.get("version_start_including")
    row.version_start_excluding = kwargs.get("version_start_excluding")
    row.version_end_including = kwargs.get("version_end_including")
    row.version_end_excluding = kwargs.get("version_end_excluding")
    row.vulnerable = kwargs.get("vulnerable", True)
    return row


def _matcher_with_rows(rows: list[MagicMock]) -> CpeMatcher:
    """Build a matcher whose session returns ``rows`` for the criteria query
    and no existing cache row for the write-back lookup."""
    criteria_result = MagicMock()
    criteria_result.scalars.return_value.all.return_value = rows

    cache_result = MagicMock()
    cache_result.scalar_one_or_none.return_value = None

    session = MagicMock()
    # First execute() → criteria fetch; second → cache write-back lookup.
    session.execute = AsyncMock(side_effect=[criteria_result, cache_result])
    session.add = MagicMock()

    alias_repo = MagicMock()
    alias_repo.resolve = AsyncMock(return_value="apache")

    return CpeMatcher(session, alias_repo=alias_repo)


@pytest.mark.asyncio
async def test_pipeline_medium_confidence_range_match() -> None:
    rows = [_criterion_row(version_start_including="2.0", version_end_excluding="2.15.0")]
    matcher = _matcher_with_rows(rows)

    matches = await matcher.match(vendor="Apache", product="log4j", version="2.14.1")

    assert len(matches) == 1
    assert isinstance(matches[0], CpeMatch)
    assert matches[0].cve_id == "CVE-2021-44228"
    assert matches[0].confidence == "medium"
    assert matches[0].version_in_range is True
    # Write-back inserted a fresh cache row.
    matcher._session.add.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pipeline_drops_out_of_range_versions() -> None:
    rows = [_criterion_row(version_start_including="2.0", version_end_excluding="2.15.0")]
    matcher = _matcher_with_rows(rows)

    matches = await matcher.match(
        vendor="Apache", product="log4j", version="2.17.0", write_back=False
    )

    assert matches == []


@pytest.mark.asyncio
async def test_pipeline_needs_review_on_unparseable_version() -> None:
    rows = [_criterion_row(version_start_including="2.0", version_end_excluding="2.15.0")]
    matcher = _matcher_with_rows(rows)

    matches = await matcher.match(
        vendor="Apache", product="log4j", version="mystery", write_back=False
    )

    assert len(matches) == 1
    assert matches[0].confidence == "needs_review"


@pytest.mark.asyncio
async def test_pipeline_skips_non_vulnerable_rows() -> None:
    rows = [_criterion_row(vulnerable=False)]
    matcher = _matcher_with_rows(rows)

    matches = await matcher.match(
        vendor="Apache", product="log4j", version="2.14.1", write_back=False
    )

    assert matches == []
