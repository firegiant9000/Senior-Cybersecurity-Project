#!/usr/bin/env python3
"""Check the STRIDE threat model (docs/security/threat_model.md) against the repo.

Usage: check_threat_model.py <doc.md> [--repo-root PATH]

Exits 0 when valid; exits 1 and prints one ::error:: line per problem otherwise.

Every table whose header is exactly `ID | STRIDE | Threat | Class | Evidence | Notes`
is checked (a near-miss header is itself an error). Lines inside code fences are ignored.
CONTROL rows must cite `path::symbol` (Lnn) evidence that exists in the repo (the line
number is informational). TEST rows must cite a test that is defined in a test file; AUTH
and TEN tests also need a `real-verification:` token in Notes (at the start or after
`; `). ACCEPTED rows need reason/owner and a review date that is neither past nor more
than 365 days out. OPEN rows need a milestone and an item. Rows whose Notes start with
`withdrawn: <reason>` skip the evidence checks.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HEADER_COLUMNS = ("ID", "STRIDE", "Threat", "Class", "Evidence", "Notes")
HEADER_TEXT = "ID | STRIDE | Threat | Class | Evidence | Notes"
ID_RE = re.compile(r"^T-(ENR|UPL|TOK|RPL|AUTH|TEN|ING|DOM|AI|REL|CI|PLAT)-\d{2}$")
STRIDE = ("S", "T", "R", "I", "D", "E")
CLASSES = ("CONTROL", "TEST", "ACCEPTED", "OPEN")
MAX_REVIEW_WINDOW = timedelta(days=365)
# Lazy path so a drive letter ("C:/x.py::y") is captured and can be rejected as outside repo.
EVIDENCE_RE = re.compile(r"`([^`\s]+?)::([^`]+)`")
LINE_HINT_RE = re.compile(r"\s*\(L\d+\)")
TEST_FILE_RE = re.compile(r"^(test_.+\.py|.+_test\.py|.+_test\.go)$")
NO_TABLES = f"no threat tables found (header must be: {HEADER_TEXT})"


@dataclass(frozen=True)
class Row:
    id: str
    stride: str
    threat: str
    cls: str
    evidence: str
    notes: str
    line: int


def _label(row: Row) -> str:
    return row.id or f"line {row.line}"


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
    in_fence = False
    for n, raw in enumerate(text.replace("\r", "").split("\n"), start=1):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            in_fence = not in_fence
            in_table = False
            continue
        if in_fence:
            continue
        if not line or "|" not in line:
            in_table = False
            continue
        cells = _cells(line)
        if tuple(cells) == HEADER_COLUMNS:
            in_table = True
            continue
        if cells[0] == "ID" or "STRIDE" in cells:
            in_table = False
            problems.append(f"line {n}: threat table header must be exactly: {HEADER_TEXT}")
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


def _class_body(text: str, cls: str) -> str | None:
    """Lines after `class cls` up to the next non-blank line indented at or below it."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.match(rf"^(\s*)class\s+{re.escape(cls)}\b", line)
        if not m:
            continue
        indent = len(m.group(1))
        body = []
        for nxt in lines[i + 1 :]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        return "\n".join(body)
    return None


def _check_control(row: Row, repo_root: Path) -> list[str]:
    refs = list(EVIDENCE_RE.finditer(row.evidence))
    if not refs:
        return [f"{_label(row)}: CONTROL needs evidence `path::symbol` (Lnn)"]
    problems = []
    for m in refs:
        path, symbol = m.group(1), m.group(2)
        if not LINE_HINT_RE.match(row.evidence[m.end() :]):
            problems.append(f"{_label(row)}: `{path}::{symbol}` needs a (L<digits>) line hint")
        full, err = _resolve(path, repo_root)
        if err:
            problems.append(f"{_label(row)}: {err}")
            continue
        segs = [s for s in symbol.split(".") if s]
        if not segs:
            problems.append(f"{_label(row)}: empty symbol in `{path}::{symbol}`")
            continue
        body = _read(full)
        for seg in segs:
            if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(seg)}(?![A-Za-z0-9_])", body):
                problems.append(f"{_label(row)}: symbol {seg!r} not found in {path}")
    return problems


def _check_test(row: Row, repo_root: Path) -> list[str]:
    refs = list(EVIDENCE_RE.finditer(row.evidence))
    label = _label(row)
    if not refs:
        return [f"{label}: TEST needs evidence `path::test_name`"]
    problems = []
    for m in refs:
        path, symbol = m.group(1), m.group(2)
        full, err = _resolve(path, repo_root)
        if err:
            problems.append(f"{label}: {err}")
            continue
        if not TEST_FILE_RE.match(full.name):
            problems.append(f"{label}: {path} is not a test file (test_*.py, *_test.py, *_test.go)")
            continue
        parts = [p for p in symbol.split("::") if p]
        if not parts:
            problems.append(f"{label}: empty test name in `{path}::{symbol}`")
            continue
        *classes, name = parts
        scope: str | None = _read(full)
        for cls in classes:
            scope = _class_body(scope, cls)
            if scope is None:
                problems.append(f"{label}: class {cls!r} not found in {path}")
                break
        if scope is None:
            continue
        py = rf"^\s*(async\s+)?def\s+{re.escape(name)}\s*\("
        go = rf"^func\s+{re.escape(name)}\s*\("
        if not (re.search(py, scope, re.MULTILINE) or re.search(go, scope, re.MULTILINE)):
            where = f"class {classes[-1]} in {path}" if classes else path
            problems.append(f"{label}: test {name!r} not defined in {where}")
    area = row.id.split("-")[1] if ID_RE.match(row.id) else ""
    if area in ("AUTH", "TEN") and not re.search(r"(^|;\s*)real-verification:", row.notes):
        problems.append(
            f"{label}: {area} TEST rows need 'real-verification:' in Notes (no mock-only proof)"
        )
    return problems


def _check_accepted(row: Row, today: date) -> list[str]:
    label = _label(row)
    problems = []
    if not re.search(r"\breason:\s*\S", row.evidence):
        problems.append(f"{label}: ACCEPTED needs 'reason: ...'")
    if not re.search(r"\bowner:\s*\S", row.evidence):
        problems.append(f"{label}: ACCEPTED needs 'owner: ...'")
    m = re.search(r"\breview:\s*(\d{4}-\d{2}-\d{2})(?!\d)", row.evidence)
    if not m:
        problems.append(f"{label}: ACCEPTED needs 'review: YYYY-MM-DD'")
    else:
        try:
            reviewed = date.fromisoformat(m.group(1))
        except ValueError:
            problems.append(f"{label}: bad review date {m.group(1)!r}")
        else:
            if reviewed < today:
                problems.append(
                    f"{label}: review date {m.group(1)} has passed (today {today.isoformat()})"
                )
            elif reviewed - today > MAX_REVIEW_WINDOW:
                problems.append(f"{label}: review date {m.group(1)} is more than 365 days out")
    return problems


def _check_open(row: Row) -> list[str]:
    label = _label(row)
    problems = []
    if not re.search(r"\bmilestone:\s*(S4|S5|S6|OWNER)\b", row.evidence):
        problems.append(f"{label}: OPEN needs 'milestone: S4|S5|S6|OWNER'")
    if not re.search(r"\bitem:\s*\S", row.evidence):
        problems.append(f"{label}: OPEN needs 'item: ...'")
    return problems


def check(text: str, repo_root: Path, today: date) -> list[str]:
    rows, problems = parse(text)
    if not rows and not problems:
        return [NO_TABLES]
    seen: dict[str, int] = {}
    for row in rows:
        label = _label(row)
        if not ID_RE.match(row.id):
            problems.append(f"{label}: invalid id {row.id!r} (line {row.line})")
        elif row.id in seen:
            problems.append(f"{label}: duplicate id (first at line {seen[row.id]})")
        else:
            seen[row.id] = row.line
        if row.stride not in STRIDE:
            problems.append(f"{label}: STRIDE {row.stride!r} not one of {'/'.join(STRIDE)}")
        if row.cls not in CLASSES:
            problems.append(f"{label}: Class {row.cls!r} not one of {'/'.join(CLASSES)}")
            continue
        if row.notes.startswith("withdrawn:"):
            if not re.match(r"withdrawn:\s*\S", row.notes):
                problems.append(f"{label}: 'withdrawn:' needs a reason")
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
    withdrawn = [r for r in rows if r.notes.startswith("withdrawn:")]
    active = [r for r in rows if not r.notes.startswith("withdrawn:")]
    counts = ", ".join(f"{c}={sum(r.cls == c for r in active)}" for c in CLASSES)
    print(f"threat model OK: {len(active)} threats ({counts}), {len(withdrawn)} withdrawn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
