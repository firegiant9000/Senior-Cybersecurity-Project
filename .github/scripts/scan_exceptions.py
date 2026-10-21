"""Parse and check the scanner exception list (docs/security/scan_exceptions.md)."""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

SCANNERS = (
    "pip-audit",
    "npm-audit",
    "govulncheck",
    "trivy",
    "codeql",
    "semgrep",
    "alembic-check",
)
COLUMNS = 7
SECTION_HEADING = "## Exceptions"
HEADER_COLUMNS = (
    "ID",
    "Scanner",
    "Package / location",
    "Reason",
    "Compensating control",
    "Added",
    "Expires",
)
MAX_WINDOW = timedelta(days=90)
DEFAULT_FILE = "docs/security/scan_exceptions.md"


@dataclass(frozen=True)
class ScanException:
    id: str
    scanner: str
    location: str
    reason: str
    control: str
    added: date
    expires: date


def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(c and set(c) <= set("-: ") for c in cells)


def _parse_date(value: str, label: str, row: str) -> date:
    # Python 3.11 fromisoformat also accepts "20261020" and "2026-W43-3"; require the plain form.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{row}: bad {label} date {value!r} (expected YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{row}: bad {label} date {value!r} (expected YYYY-MM-DD)") from None


def parse_exceptions(markdown: str) -> list[ScanException]:
    lines = markdown.splitlines()
    in_fence = False
    start = -1
    count = 0
    for i, raw in enumerate(lines):
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and raw.rstrip() == SECTION_HEADING:
            count += 1
            if start < 0:
                start = i
    if count != 1:
        raise ValueError(f"expected exactly one {SECTION_HEADING!r} heading, found {count}")

    # Table rows of the section: from the heading to the next heading outside a code fence.
    table: list[str] = []
    in_fence = False
    for raw in lines[start + 1 :]:
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("#"):
            break
        if line.startswith("|"):
            table.append(line)

    if len(table) < 2:
        raise ValueError("Exceptions table is missing its header and separator rows")
    if _cells(table[0]) != list(HEADER_COLUMNS):
        raise ValueError(f"Exceptions table header must be exactly: {' | '.join(HEADER_COLUMNS)}")
    if not _is_separator(_cells(table[1])):
        raise ValueError("Exceptions table header must be followed by a '| --- |' separator row")

    entries: list[ScanException] = []
    for line in table[2:]:
        cells = _cells(line)
        if _is_separator(cells):
            continue
        row = f"row {cells[0]!r}" if cells and cells[0] else f"row {line!r}"
        if len(cells) != COLUMNS:
            raise ValueError(f"{row}: expected {COLUMNS} cells, got {len(cells)}: {line!r}")
        id_, scanner, location, reason, control, added, expires = cells
        if scanner not in SCANNERS:
            raise ValueError(f"{row}: unknown scanner {scanner!r}")
        entries.append(
            ScanException(
                id_,
                scanner,
                location,
                reason,
                control,
                _parse_date(added, "Added", row),
                _parse_date(expires, "Expires", row),
            )
        )
    return entries


def validate(entries: list[ScanException], today: date) -> list[str]:
    errors = []
    for e in entries:
        if e.added > today:
            errors.append(f"{e.id}: added {e.added} is in the future (today {today})")
        if e.expires < e.added:
            errors.append(f"{e.id}: expires {e.expires} is before added {e.added}")
        elif e.expires - e.added > MAX_WINDOW:
            errors.append(
                f"{e.id}: window {(e.expires - e.added).days} days exceeds 90 (added {e.added}, expires {e.expires})"
            )
        if e.expires < today:
            errors.append(f"{e.id}: expired on {e.expires} (today {today})")
    return errors


def active_ids(entries: list[ScanException], scanner: str, today: date) -> list[str]:
    return [e.id for e in entries if e.scanner == scanner and e.expires >= today]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("--file", default=DEFAULT_FILE)
    ids = sub.add_parser("ids")
    ids.add_argument("scanner", choices=SCANNERS)
    ids.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args(argv)

    today = datetime.now(timezone.utc).date()
    try:
        with open(args.file, encoding="utf-8") as f:
            entries = parse_exceptions(f.read())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.cmd == "check":
        errors = validate(entries, today)
        for err in errors:
            print(f"error: {err}")
        return 1 if errors else 0
    for id_ in active_ids(entries, args.scanner, today):
        print(id_)
    return 0


if __name__ == "__main__":
    sys.exit(main())
