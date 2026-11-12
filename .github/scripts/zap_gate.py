#!/usr/bin/env python3
"""Fail when a ZAP JSON report has medium or high alerts not covered by an active exception.

Usage: zap_gate.py <zap-report.json> <scan_exceptions.md>

Exits 0 when no alert with riskcode >= 2 remains after removing plugin ids that are active
`zap` entries in the exception list (expired entries do not count). Otherwise exits 1 and
prints one line per failing alert: `pluginid riskdesc name (N instances)`.
"""

import json
import sys
from datetime import datetime, timezone

import scan_exceptions

MIN_FAIL_RISK = 2  # ZAP riskcode: 0 info, 1 low, 2 medium, 3 high


def _sites(report: dict) -> list[dict] | None:
    """The report's site objects, or None when `site` is missing/malformed or holds a non-object."""
    site = report.get("site")
    if isinstance(site, dict):
        return [site]
    if isinstance(site, list) and all(isinstance(s, dict) for s in site):
        return site
    return None


def _well_formed(report: object) -> bool:
    """At least one site; every site has an `alerts` list of objects."""
    if not isinstance(report, dict):
        return False
    sites = _sites(report)
    if not sites:
        return False
    return all(isinstance(s.get("alerts"), list) and all(isinstance(a, dict) for a in s["alerts"]) for s in sites)


def _risk(alert: dict) -> int | None:
    try:
        return int(alert["riskcode"])
    except (KeyError, TypeError, ValueError):
        return None


def failing_alerts(report: dict, ignored: set[str]) -> list[dict]:
    """Alerts with riskcode >= 2 not ignored, plus any alert whose riskcode is missing or non-numeric."""
    failing = []
    for site in _sites(report) or []:
        for a in site.get("alerts") or []:
            risk = _risk(a)
            if risk is None or (risk >= MIN_FAIL_RISK and str(a.get("pluginid")) not in ignored):
                failing.append(a)
    return failing


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: zap_gate.py <zap-report.json> <scan_exceptions.md>", file=sys.stderr)
        return 2
    report_path, exceptions_path = args
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        with open(exceptions_path, encoding="utf-8") as f:
            entries = scan_exceptions.parse_exceptions(f.read())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not _well_formed(report):
        print("error: ZAP report is empty or malformed (need site entries, each with an alerts list)", file=sys.stderr)
        return 1

    today = datetime.now(timezone.utc).date()
    ignored = set(scan_exceptions.active_ids(entries, "zap", today))
    failing = failing_alerts(report, ignored)
    for a in failing:
        if _risk(a) is None:
            print(f"error: alert {a.get('pluginid')} has a missing or non-numeric riskcode", file=sys.stderr)
        print(f"{a.get('pluginid')} {a.get('riskdesc', '')} {a.get('name', '')} ({len(a.get('instances', []))} instances)")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
