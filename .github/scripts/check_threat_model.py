#!/usr/bin/env python3
"""Check the STRIDE threat model (docs/security/threat_model.md) against the repo.

Usage: check_threat_model.py <doc.md> [--repo-root PATH]

Exits 0 when valid; exits 1 and prints one ::error:: line per problem otherwise.

Every table whose header is exactly `ID | STRIDE | Threat | Class | Evidence | Notes`
is checked. CONTROL and TEST rows must cite `path::symbol` evidence that exists in the
repo, ACCEPTED rows need reason/owner/an unexpired review date, OPEN rows need a
milestone and an item. Rows whose Notes start with `withdrawn:` skip the evidence checks.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

HEADER_COLUMNS = ("ID", "STRIDE", "Threat", "Class", "Evidence", "Notes")
ID_RE = re.compile(r"^T-(ENR|UPL|TOK|RPL|AUTH|TEN|ING|AI|REL|CI|PLAT)-\d{2}$")
STRIDE = ("S", "T", "R", "I", "D", "E")
CLASSES = ("CONTROL", "TEST", "ACCEPTED", "OPEN")
# Lazy path so a drive letter ("C:/x.py::y") is captured and can be rejected as outside repo.
EVIDENCE_RE = re.compile(r"`([^`\s]+?)::([^`]+)`")
NO_TABLES = "no threat tables found (header must be: ID | STRIDE | Threat | Class | Evidence | Notes)"


@dataclass(frozen=True)
class Row:
    id: str
    stride: str
    threat: str
    cls: str
    evidence: str
    notes: str
    line: int


def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(c and set(c) <= set("-: ") for c in cells)


def parse(text: str) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    problems: list[str] = []
    in_table = False
    for n, raw in enumerate(text.replace("\r", "").split("\n"), start=1):
        line = raw.strip()
        if not line:
            in_table = False
            continue
        if "|" not in line:
            in_table = False
            continue
        cells = _cells(line)
        if tuple(cells) == HEADER_COLUMNS:
            in_table = True
            continue
        if not in_table or _is_separator(cells):
            continue
        if len(cells) != len(HEADER_COLUMNS):
            problems.append(
                f"line {n}: expected {len(HEADER_COLUMNS)} cells, got {len(cells)}"
                " (a literal '|' inside a cell shifts the columns)"
            )
            continue
        rows.append(Row(*cells, line=n))
    return rows, problems


def _resolve(path: str, repo_root: Path) -> tuple[Path | None, str | None]:
    """Return (file, None) or (None, problem). Rejects escapes before touching the disk."""
    segments = re.split(r"[\\/]", path)
    if (
        path.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", path)
        or ".." in segments
    ):
        return None, f"path {path!r} is outside repo"
    root = repo_root.resolve()
    try:
        full = (root / path).resolve()
        full.relative_to(root)
    except (OSError, ValueError):
        return None, f"path {path!r} is outside repo"
    if not full.is_file():
        return None, f"path {path!r} does not exist"
    return full, None


def _read(full: Path) -> str:
    return full.read_text(encoding="utf-8", errors="replace")


def _check_control(row: Row, repo_root: Path) -> list[str]:
    refs = EVIDENCE_RE.findall(row.evidence)
    if not refs:
        return [f"{row.id}: CONTROL needs evidence `path::symbol`"]
    problems = []
    for path, symbol in refs:
        full, err = _resolve(path, repo_root)
        if err:
            problems.append(f"{row.id}: {err}")
            continue
        body = _read(full)
        for seg in symbol.split("."):
            if seg and seg not in body:
                problems.append(f"{row.id}: symbol {seg!r} not found in {path}")
    return problems


def _check_test(row: Row, repo_root: Path) -> list[str]:
    refs = EVIDENCE_RE.findall(row.evidence)
    if not refs:
        return [f"{row.id}: TEST needs evidence `path::test_name`"]
    problems = []
    for path, symbol in refs:
        full, err = _resolve(path, repo_root)
        if err:
            problems.append(f"{row.id}: {err}")
            continue
        body = _read(full)
        *classes, name = [p for p in symbol.split("::") if p]
        for cls in classes:
            if not re.search(rf"^\s*class\s+{re.escape(cls)}\b", body, re.MULTILINE):
                problems.append(f"{row.id}: class {cls!r} not found in {path}")
        py = rf"^\s*(async\s+)?def\s+{re.escape(name)}\s*\("
        go = rf"^func\s+{re.escape(name)}\s*\("
        if not (re.search(py, body, re.MULTILINE) or re.search(go, body, re.MULTILINE)):
            problems.append(f"{row.id}: test {name!r} not defined in {path}")
    area = row.id.split("-")[1] if row.id.count("-") == 2 else ""
    if area in ("AUTH", "TEN") and "real-verification" not in row.notes:
        problems.append(
            f"{row.id}: {area} TEST rows need 'real-verification' in Notes (no mock-only proof)"
        )
    return problems


def _check_accepted(row: Row, today: date) -> list[str]:
    problems = []
    if not re.search(r"reason:\s*\S", row.evidence):
        problems.append(f"{row.id}: ACCEPTED needs 'reason: ...'")
    if not re.search(r"owner:\s*\S", row.evidence):
        problems.append(f"{row.id}: ACCEPTED needs 'owner: ...'")
    m = re.search(r"review:\s*(\d{4}-\d{2}-\d{2})", row.evidence)
    if not m:
        problems.append(f"{row.id}: ACCEPTED needs 'review: YYYY-MM-DD'")
    else:
        try:
            reviewed = date.fromisoformat(m.group(1))
        except ValueError:
            problems.append(f"{row.id}: bad review date {m.group(1)!r}")
        else:
            if reviewed < today:
                problems.append(
                    f"{row.id}: review date {m.group(1)} has passed (today {today.isoformat()})"
                )
    return problems


def _check_open(row: Row) -> list[str]:
    problems = []
    if not re.search(r"milestone:\s*(S4|S5|S6|OWNER)\b", row.evidence):
        problems.append(f"{row.id}: OPEN needs 'milestone: S4|S5|S6|OWNER'")
    if not re.search(r"item:\s*\S", row.evidence):
        problems.append(f"{row.id}: OPEN needs 'item: ...'")
    return problems


def check(text: str, repo_root: Path, today: date) -> list[str]:
    rows, problems = parse(text)
    if not rows and not problems:
        return [NO_TABLES]
    seen: dict[str, int] = {}
    for row in rows:
        if not ID_RE.match(row.id):
            problems.append(f"{row.id or 'line ' + str(row.line)}: invalid id (line {row.line})")
        elif row.id in seen:
            problems.append(f"{row.id}: duplicate id (first at line {seen[row.id]})")
        else:
            seen[row.id] = row.line
        if row.stride not in STRIDE:
            problems.append(f"{row.id}: STRIDE {row.stride!r} not one of {'/'.join(STRIDE)}")
        if row.cls not in CLASSES:
            problems.append(f"{row.id}: Class {row.cls!r} not one of {'/'.join(CLASSES)}")
            continue
        if row.notes.startswith("withdrawn:"):
            continue
        if row.cls == "CONTROL":
            problems += _check_control(row, repo_root)
        elif row.cls == "TEST":
            problems += _check_test(row, repo_root)
        elif row.cls == "ACCEPTED":
            problems += _check_accepted(row, today)
        else:
            problems += _check_open(row)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("doc")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)

    try:
        text = Path(args.doc).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"::error::cannot read {args.doc}: {exc}")
        return 1

    today = datetime.now(timezone.utc).date()
    problems = check(text, args.repo_root, today)
    for p in problems:
        print(f"::error::{p}")
    if problems:
        return 1
    rows, _ = parse(text)
    counts = ", ".join(f"{c}={sum(r.cls == c for r in rows)}" for c in CLASSES)
    print(f"threat model OK: {len(rows)} threats ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
