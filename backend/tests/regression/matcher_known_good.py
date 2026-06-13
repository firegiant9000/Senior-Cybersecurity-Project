"""Month 3, Phase 5 — CPE matcher regression harness ("known-good" set).

This drives the Phase 2 matcher (``CpeMatcher.match``) through a catalog of
real KEV/NVD CVEs with published affected-version ranges, asserting that each
``(vendor, product, version)`` resolves to the expected CVE set at the expected
confidence tier. It is the calibration gate that protects against silent
matcher drift — the roadmap principle is that *a high-confidence false positive
erodes trust permanently*, so the gate enforces both a pass rate and a hard cap
on the high-confidence false-positive rate.

The harness is intentionally DB-free: each case is run against an in-memory
criteria catalog through a fake session (the same mocking shape as
``tests/test_cpe_matcher.py``), so the nightly CI job needs no Postgres and runs
in milliseconds. The collectable assertions live in
``test_matcher_known_good.py``; running this module directly prints a human
calibration report and exits non-zero on a gate breach.

Calibration gate (roadmap Checkpoint 2):
* ``MIN_PASS_RATE``           — ≥ 95% of cases resolve to the expected CVE set.
* ``MAX_HIGH_CONF_FP_RATE``   — < 2% of high-confidence matches are false positives.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

from app.services.cpe_matcher import CpeMatcher, normalize_cpe_token

# --- Calibration thresholds ------------------------------------------------

MIN_PASS_RATE = 0.95
MAX_HIGH_CONF_FP_RATE = 0.02

# Vendor display-name → canonical vendor, mirroring what ``vendor_aliases``
# resolves in production so the harness exercises name normalization too.
ALIAS_MAP: dict[str, str] = {
    "the apache software foundation": "apache",
    "apache software foundation": "apache",
    "apache foundation": "apache",
    "vmware, inc.": "vmware",
    "pivotal": "vmware",
    "openssl software foundation": "openssl",
}


# --- Catalog model ---------------------------------------------------------


@dataclass(frozen=True)
class Criterion:
    """One CPE criterion as stored in ``cve_cpe_match`` (the fields the matcher reads)."""

    cve_id: str
    cpe_uri: str
    version_start_including: str | None = None
    version_start_excluding: str | None = None
    version_end_including: str | None = None
    version_end_excluding: str | None = None
    vulnerable: bool = True


@dataclass(frozen=True)
class Case:
    """A known-good expectation: software identity → CVE set at a confidence tier."""

    label: str
    tier: str  # documents the intended confidence tier for this case
    vendor: str
    product: str
    version: str | None
    expected: frozenset[str]
    # cve_id → expected confidence; checked for the CVEs that should match.
    expected_confidence: dict[str, str] = field(default_factory=dict)
    cpe_uri: str | None = None


def _c(vendor: str, product: str, *criteria: Criterion) -> tuple[tuple[str, str], list[Criterion]]:
    return ((normalize_cpe_token(vendor), normalize_cpe_token(product)), list(criteria))


# --- Criteria catalog (CVE → affected-version ranges) ----------------------
# Ranges are drawn from the published NVD CPE configurations for these CVEs.

CRITERIA_CATALOG: dict[tuple[str, str], list[Criterion]] = dict(
    [
        _c(
            "apache",
            "log4j",
            Criterion(
                "CVE-2021-44228",
                "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                version_start_including="2.0-beta9",
                version_end_excluding="2.15.0",
            ),
            Criterion(
                "CVE-2021-45046",
                "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                version_start_including="2.0",
                version_end_excluding="2.16.0",
            ),
            Criterion(
                "CVE-2021-45105",
                "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                version_start_including="2.0",
                version_end_excluding="2.17.0",
            ),
        ),
        _c(
            "openssl",
            "openssl",
            Criterion(
                "CVE-2014-0160",  # Heartbleed
                "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*",
                version_start_including="1.0.1",
                version_end_including="1.0.1f",
            ),
            Criterion(
                "CVE-2022-3786",  # punycode buffer overflow
                "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*",
                version_start_including="3.0.0",
                version_end_excluding="3.0.7",
            ),
            Criterion(
                "CVE-2016-2107",  # concrete affected version, no range
                "cpe:2.3:a:openssl:openssl:1.0.2:*:*:*:*:*:*:*",
            ),
        ),
        _c(
            "apache",
            "struts",
            Criterion(
                "CVE-2017-5638",
                "cpe:2.3:a:apache:struts:*:*:*:*:*:*:*:*",
                version_start_including="2.3.5",
                version_end_excluding="2.3.32",
            ),
            Criterion(
                "CVE-2017-5638",  # second affected branch, same CVE
                "cpe:2.3:a:apache:struts:*:*:*:*:*:*:*:*",
                version_start_including="2.5",
                version_end_excluding="2.5.10.1",
            ),
        ),
        _c(
            "apache",
            "http_server",
            Criterion(
                "CVE-2021-41773",  # concrete affected version
                "cpe:2.3:a:apache:http_server:2.4.49:*:*:*:*:*:*:*",
            ),
            Criterion(
                "CVE-2021-42013",
                "cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*",
                version_start_including="2.4.49",
                version_end_including="2.4.50",
            ),
        ),
        _c(
            "vmware",
            "spring_framework",
            Criterion(
                "CVE-2022-22965",  # Spring4Shell
                "cpe:2.3:a:vmware:spring_framework:*:*:*:*:*:*:*:*",
                version_start_including="5.3.0",
                version_end_excluding="5.3.18",
            ),
            Criterion(
                "CVE-2022-22965",
                "cpe:2.3:a:vmware:spring_framework:*:*:*:*:*:*:*:*",
                version_start_including="5.2.0",
                version_end_excluding="5.2.20",
            ),
        ),
        _c(
            "atlassian",
            "confluence_server",
            Criterion(
                "CVE-2022-26134",
                "cpe:2.3:a:atlassian:confluence_server:*:*:*:*:*:*:*:*",
                version_start_including="1.3.0",
                version_end_excluding="7.18.1",
            ),
        ),
        _c(
            "citrix",
            "application_delivery_controller",
            # Version-agnostic: NVD lists every version as vulnerable.
            Criterion(
                "CVE-2019-19781",
                "cpe:2.3:a:citrix:application_delivery_controller:*:*:*:*:*:*:*:*",
            ),
        ),
        _c(
            "fortinet",
            "fortios",
            Criterion(
                "CVE-2018-13379",
                "cpe:2.3:o:fortinet:fortios:*:*:*:*:*:*:*:*",
                version_start_including="6.0.0",
                version_end_including="6.0.4",
            ),
        ),
        _c(
            "nginx",
            "nginx",
            Criterion(
                "CVE-2019-20372",
                "cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*",
                version_start_including="0.7.12",
                version_end_excluding="1.17.7",
            ),
        ),
    ]
)


# --- Known-good cases ------------------------------------------------------

CASES: list[Case] = [
    # ---- Log4j: range matches (medium) and the famous boundary at 2.15.0 ----
    Case(
        "log4j 2.14.1 vulnerable to all three",
        "medium",
        "apache",
        "log4j",
        "2.14.1",
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
        {
            "CVE-2021-44228": "medium",
            "CVE-2021-45046": "medium",
            "CVE-2021-45105": "medium",
        },
    ),
    Case(
        "log4j 2.15.0 patched for 44228, still in 45046/45105",
        "medium",
        "apache",
        "log4j",
        "2.15.0",
        frozenset({"CVE-2021-45046", "CVE-2021-45105"}),
        {"CVE-2021-45046": "medium", "CVE-2021-45105": "medium"},
    ),
    Case(
        "log4j 2.16.0 only 45105 remains",
        "medium",
        "apache",
        "log4j",
        "2.16.0",
        frozenset({"CVE-2021-45105"}),
        {"CVE-2021-45105": "medium"},
    ),
    Case(
        "log4j 2.17.0 fully patched (negative)",
        "negative",
        "apache",
        "log4j",
        "2.17.0",
        frozenset(),
    ),
    Case(
        "log4j 1.2.17 predates the range (negative)",
        "negative",
        "apache",
        "log4j",
        "1.2.17",
        frozenset(),
    ),
    Case(
        "log4j 2.0-beta9 inclusive lower bound",
        "medium",
        "apache",
        "log4j",
        "2.0-beta9",
        frozenset({"CVE-2021-44228"}),
        {"CVE-2021-44228": "medium"},
    ),
    Case(
        "log4j vendor alias normalizes to apache",
        "medium",
        "The Apache Software Foundation",
        "log4j",
        "2.10.0",
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
    ),
    Case(
        "log4j no version supplied → needs_review (range requires a version)",
        "needs_review",
        "apache",
        "log4j",
        None,
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
        {
            "CVE-2021-44228": "needs_review",
            "CVE-2021-45046": "needs_review",
            "CVE-2021-45105": "needs_review",
        },
    ),
    Case(
        "log4j unparseable version → needs_review",
        "needs_review",
        "apache",
        "log4j",
        "latest-snapshot-build",
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
        {
            "CVE-2021-44228": "needs_review",
            "CVE-2021-45046": "needs_review",
            "CVE-2021-45105": "needs_review",
        },
    ),
    Case(
        # The asset CPE pins only a wildcard version (`log4j:*`), so it shares a
        # CPE core with the wildcard-range criterion but agrees only on
        # vendor/product — NOT on a concrete version. That must stay `medium`
        # (name normalized + version-in-range), never inflate to `high`, or it
        # becomes the version-blind false positive the roadmap forbids.
        "log4j wildcard asset CPE stays medium (no version-blind high)",
        "medium",
        "apache",
        "log4j",
        "2.14.1",
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
        {
            "CVE-2021-44228": "medium",
            "CVE-2021-45046": "medium",
            "CVE-2021-45105": "medium",
        },
        cpe_uri="cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
    ),
    # ---- OpenSSL: end-including bound, concrete-version equality (high) ----
    Case(
        "openssl 1.0.1 lower bound (Heartbleed)",
        "medium",
        "openssl",
        "openssl",
        "1.0.1",
        frozenset({"CVE-2014-0160"}),
        {"CVE-2014-0160": "medium"},
    ),
    Case(
        "openssl 1.0.1f inclusive upper bound",
        "medium",
        "openssl",
        "openssl",
        "1.0.1f",
        frozenset({"CVE-2014-0160"}),
        {"CVE-2014-0160": "medium"},
    ),
    Case(
        "openssl 1.0.1g patched (negative)",
        "negative",
        "openssl",
        "openssl",
        "1.0.1g",
        frozenset(),
    ),
    Case(
        "openssl 1.0.0 below range (negative)",
        "negative",
        "openssl",
        "openssl",
        "1.0.0",
        frozenset(),
    ),
    Case(
        "openssl 3.0.5 punycode range",
        "medium",
        "openssl",
        "openssl",
        "3.0.5",
        frozenset({"CVE-2022-3786"}),
        {"CVE-2022-3786": "medium"},
    ),
    Case(
        "openssl 3.0.7 patched punycode (negative)",
        "negative",
        "openssl",
        "openssl",
        "3.0.7",
        frozenset(),
    ),
    Case(
        "openssl 1.0.2 concrete-version equality → high",
        "high",
        "openssl",
        "openssl",
        "1.0.2",
        frozenset({"CVE-2016-2107"}),
        {"CVE-2016-2107": "high"},
    ),
    Case(
        "openssl 1.0.2h not equal to concrete 1.0.2 (negative)",
        "negative",
        "openssl",
        "openssl",
        "1.0.2h",
        frozenset(),
    ),
    Case(
        "openssl vendor alias normalizes",
        "medium",
        "OpenSSL Software Foundation",
        "openssl",
        "1.0.1c",
        frozenset({"CVE-2014-0160"}),
    ),
    # ---- Struts: two affected branches under one CVE ----
    Case(
        "struts 2.3.10 hits the 2.3.x branch",
        "medium",
        "apache",
        "struts",
        "2.3.10",
        frozenset({"CVE-2017-5638"}),
        {"CVE-2017-5638": "medium"},
    ),
    Case(
        "struts 2.5.5 hits the 2.5.x branch",
        "medium",
        "apache",
        "struts",
        "2.5.5",
        frozenset({"CVE-2017-5638"}),
        {"CVE-2017-5638": "medium"},
    ),
    Case(
        "struts 2.3.32 patched on 2.3.x branch (negative)",
        "negative",
        "apache",
        "struts",
        "2.3.32",
        frozenset(),
    ),
    Case(
        "struts 2.5.10.1 patched on 2.5.x branch (negative)",
        "negative",
        "apache",
        "struts",
        "2.5.10.1",
        frozenset(),
    ),
    Case(
        "struts 2.4.0 between branches (negative)",
        "negative",
        "apache",
        "struts",
        "2.4.0",
        frozenset(),
    ),
    # ---- Apache httpd: concrete version (high) + range ----
    Case(
        "httpd 2.4.49 concrete + range overlap",
        "high",
        "apache",
        "http_server",
        "2.4.49",
        frozenset({"CVE-2021-41773", "CVE-2021-42013"}),
        {"CVE-2021-41773": "high", "CVE-2021-42013": "medium"},
    ),
    Case(
        "httpd 2.4.50 only path-traversal range",
        "medium",
        "apache",
        "http_server",
        "2.4.50",
        frozenset({"CVE-2021-42013"}),
        {"CVE-2021-42013": "medium"},
    ),
    Case(
        "httpd 2.4.51 patched (negative)",
        "negative",
        "apache",
        "http_server",
        "2.4.51",
        frozenset(),
    ),
    Case(
        "httpd 2.4.48 predates both (negative)",
        "negative",
        "apache",
        "http_server",
        "2.4.48",
        frozenset(),
    ),
    # ---- Spring4Shell: two maintenance branches ----
    Case(
        "spring 5.3.17 vulnerable",
        "medium",
        "vmware",
        "spring_framework",
        "5.3.17",
        frozenset({"CVE-2022-22965"}),
        {"CVE-2022-22965": "medium"},
    ),
    Case(
        "spring 5.2.19 vulnerable on 5.2 branch",
        "medium",
        "vmware",
        "spring_framework",
        "5.2.19",
        frozenset({"CVE-2022-22965"}),
        {"CVE-2022-22965": "medium"},
    ),
    Case(
        "spring 5.3.18 patched (negative)",
        "negative",
        "vmware",
        "spring_framework",
        "5.3.18",
        frozenset(),
    ),
    Case(
        "spring pivotal alias normalizes to vmware",
        "medium",
        "Pivotal",
        "spring_framework",
        "5.3.0",
        frozenset({"CVE-2022-22965"}),
    ),
    # ---- Confluence wide range ----
    Case(
        "confluence 7.4.0 in range",
        "medium",
        "atlassian",
        "confluence_server",
        "7.4.0",
        frozenset({"CVE-2022-26134"}),
        {"CVE-2022-26134": "medium"},
    ),
    Case(
        "confluence 7.18.1 patched (negative)",
        "negative",
        "atlassian",
        "confluence_server",
        "7.18.1",
        frozenset(),
    ),
    Case(
        "confluence 1.2.9 predates range (negative)",
        "negative",
        "atlassian",
        "confluence_server",
        "1.2.9",
        frozenset(),
    ),
    # ---- Citrix ADC: version-agnostic criterion (low tier) ----
    Case(
        "citrix ADC any version → low (version-agnostic CVE)",
        "low",
        "citrix",
        "application_delivery_controller",
        "13.0",
        frozenset({"CVE-2019-19781"}),
        {"CVE-2019-19781": "low"},
    ),
    Case(
        "citrix ADC no version → low",
        "low",
        "citrix",
        "application_delivery_controller",
        None,
        frozenset({"CVE-2019-19781"}),
        {"CVE-2019-19781": "low"},
    ),
    Case(
        "citrix ADC messy version still low (no range to fail)",
        "low",
        "citrix",
        "application_delivery_controller",
        "build-2020-Q1",
        frozenset({"CVE-2019-19781"}),
        {"CVE-2019-19781": "low"},
    ),
    # ---- FortiOS: OS-type CPE, inclusive upper bound ----
    Case(
        "fortios 6.0.0 lower bound",
        "medium",
        "fortinet",
        "fortios",
        "6.0.0",
        frozenset({"CVE-2018-13379"}),
        {"CVE-2018-13379": "medium"},
    ),
    Case(
        "fortios 6.0.4 inclusive upper bound",
        "medium",
        "fortinet",
        "fortios",
        "6.0.4",
        frozenset({"CVE-2018-13379"}),
        {"CVE-2018-13379": "medium"},
    ),
    Case(
        "fortios 6.0.5 patched (negative)",
        "negative",
        "fortinet",
        "fortios",
        "6.0.5",
        frozenset(),
    ),
    Case(
        "fortios 5.6.0 below range (negative)",
        "negative",
        "fortinet",
        "fortios",
        "5.6.0",
        frozenset(),
    ),
    # ---- nginx: wide range, exclusive upper ----
    Case(
        "nginx 1.17.6 vulnerable",
        "medium",
        "nginx",
        "nginx",
        "1.17.6",
        frozenset({"CVE-2019-20372"}),
        {"CVE-2019-20372": "medium"},
    ),
    Case(
        "nginx 1.17.7 patched (negative)",
        "negative",
        "nginx",
        "nginx",
        "1.17.7",
        frozenset(),
    ),
    Case(
        "nginx 0.7.11 predates range (negative)",
        "negative",
        "nginx",
        "nginx",
        "0.7.11",
        frozenset(),
    ),
    Case(
        "nginx 0.7.12 inclusive lower bound",
        "medium",
        "nginx",
        "nginx",
        "0.7.12",
        frozenset({"CVE-2019-20372"}),
        {"CVE-2019-20372": "medium"},
    ),
    Case(
        "nginx 1.18.0 patched (negative)",
        "negative",
        "nginx",
        "nginx",
        "1.18.0",
        frozenset(),
    ),
    # ---- Unknown software: no criteria at all (negative) ----
    Case(
        "unknown vendor/product → no findings (negative)",
        "negative",
        "acme",
        "doesnotexist",
        "1.0.0",
        frozenset(),
    ),
    Case(
        "known vendor, unknown product → no findings (negative)",
        "negative",
        "apache",
        "totally_made_up",
        "1.0.0",
        frozenset(),
    ),
    # ---- Numeric (not lexical) ordering guards ----
    Case(
        "nginx 1.2.0 inside range (lexical trap vs 1.17.x)",
        "medium",
        "nginx",
        "nginx",
        "1.2.0",
        frozenset({"CVE-2019-20372"}),
        {"CVE-2019-20372": "medium"},
    ),
    Case(
        "log4j 2.9.0 inside range (lexical trap vs 2.15.0)",
        "medium",
        "apache",
        "log4j",
        "2.9.0",
        frozenset({"CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105"}),
    ),
]


# --- Runner ----------------------------------------------------------------


@dataclass(frozen=True)
class CaseResult:
    case: Case
    returned: dict[str, str]  # cve_id → confidence the matcher assigned
    passed: bool
    failure_reason: str | None


@dataclass(frozen=True)
class CalibrationReport:
    results: list[CaseResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def high_conf_total(self) -> int:
        return sum(sum(1 for conf in r.returned.values() if conf == "high") for r in self.results)

    @property
    def high_conf_false_positives(self) -> int:
        fps = 0
        for r in self.results:
            for cve_id, conf in r.returned.items():
                if conf == "high" and cve_id not in r.case.expected:
                    fps += 1
        return fps

    @property
    def high_conf_fp_rate(self) -> float:
        return (
            self.high_conf_false_positives / self.high_conf_total if self.high_conf_total else 0.0
        )

    @property
    def gate_passed(self) -> bool:
        return self.pass_rate >= MIN_PASS_RATE and self.high_conf_fp_rate < MAX_HIGH_CONF_FP_RATE

    @property
    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]


def _build_matcher(rows: list[Criterion], canonical_vendor: str) -> CpeMatcher:
    """A ``CpeMatcher`` whose session returns ``rows`` for the criteria query.

    Cases run with ``write_back=False`` so the cache lookup never fires; one
    ``execute`` is enough. The alias repo is stubbed to the resolved vendor.
    """
    criteria_result = MagicMock()
    criteria_result.scalars.return_value.all.return_value = rows

    session = MagicMock()
    session.execute = AsyncMock(return_value=criteria_result)

    alias_repo = MagicMock()
    alias_repo.resolve = AsyncMock(return_value=canonical_vendor)

    return CpeMatcher(session, alias_repo=alias_repo)


async def run_case(case: Case) -> CaseResult:
    canonical_vendor = ALIAS_MAP.get(case.vendor.strip().lower(), case.vendor)
    key = (normalize_cpe_token(canonical_vendor), normalize_cpe_token(case.product))
    rows = CRITERIA_CATALOG.get(key, [])

    matcher = _build_matcher(rows, canonical_vendor)
    matches = await matcher.match(
        vendor=case.vendor,
        product=case.product,
        version=case.version,
        cpe_uri=case.cpe_uri,
        write_back=False,
    )

    returned: dict[str, str] = {m.cve_id: m.confidence for m in matches}

    failure_reason: str | None = None
    returned_cves = frozenset(returned)
    if returned_cves != case.expected:
        missing = case.expected - returned_cves
        extra = returned_cves - case.expected
        parts = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if extra:
            parts.append(f"unexpected {sorted(extra)}")
        failure_reason = "; ".join(parts)
    else:
        for cve_id, expected_conf in case.expected_confidence.items():
            actual = returned.get(cve_id)
            if actual != expected_conf:
                failure_reason = f"{cve_id} confidence was {actual!r}, expected {expected_conf!r}"
                break

    return CaseResult(
        case=case,
        returned=returned,
        passed=failure_reason is None,
        failure_reason=failure_reason,
    )


async def evaluate(cases: list[Case] | None = None) -> CalibrationReport:
    """Run every case and return a calibration report."""
    selected = cases if cases is not None else CASES
    results = [await run_case(case) for case in selected]
    return CalibrationReport(results=results)


def format_report(report: CalibrationReport) -> str:
    lines = [
        "CPE matcher regression — calibration report",
        "=" * 50,
        f"cases:                 {report.total}",
        f"passed:                {report.passed} ({report.pass_rate:.1%})",
        f"high-conf matches:     {report.high_conf_total}",
        f"high-conf FPs:         {report.high_conf_false_positives} ({report.high_conf_fp_rate:.2%})",
        f"gate (>= {MIN_PASS_RATE:.0%} pass, < {MAX_HIGH_CONF_FP_RATE:.0%} high-conf FP): "
        f"{'PASS' if report.gate_passed else 'FAIL'}",
    ]
    if report.failures:
        lines.append("-" * 50)
        lines.append("failures:")
        for r in report.failures:
            lines.append(f"  [{r.case.tier}] {r.case.label}: {r.failure_reason}")
    return "\n".join(lines)


def main() -> int:
    report = asyncio.run(evaluate())
    print(format_report(report))
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
