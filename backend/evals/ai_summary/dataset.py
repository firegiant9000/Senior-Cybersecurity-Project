"""Versioned eval dataset: case schema, manifest checks, input building (protocol §2).

A dataset directory holds `cases.jsonl` and `MANIFEST.json`. The manifest
records the SHA-256 of every file and the counts by split and category; any
mismatch refuses the load, so a scored number always maps to exact files.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.findings import Finding, FindingsReport
from app.services.findings_engine import _build_summary, _severity_score
from app.services.risk_scoring import calculate_smb_risk_score
from evals.ai_summary.config import HERE

DATASET_ROOT = HERE / "dataset"
# A three-case smoke dataset for dry runs and harness checks. Never reported.
FIXTURE_DATASET = DATASET_ROOT / "fixture"
CASES_FILE = "cases.jsonl"
MANIFEST_FILE = "MANIFEST.json"
ATTACK_CATEGORIES = frozenset({"org_injection", "finding_injection"})
# R1: a KEV finding is a vendor KEV match at critical or high severity.
KEV_SOURCE = "kev_vendor_match"
KEV_SEVERITIES = frozenset({"critical", "high"})
KEV_TOP_N = 3
# `_build_prompt` shows only report.findings[:20] (ai_summary.py:78).
PROMPT_FINDINGS_CAP = 20
# Fixed timestamp so the rendered input never depends on the wall clock.
_GENERATED_AT = "2026-01-01T00:00:00+00:00"

Split = Literal["dev", "heldout"]
Category = Literal["normal", "edge", "org_injection", "finding_injection"]


class ManifestMismatchError(Exception):
    """The dataset files do not match MANIFEST.json."""


class CaseOrg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    industry_label: str | None = None
    employee_range: str | None = None
    primary_state: str | None = None


class CaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: CaseOrg
    assessment_tier: str = "partial"
    findings: list[Finding]


class CaseExpect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kev_ids_required: list[str]
    allowed_citation_ids: list[str]


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    split: Split
    category: Category
    input: CaseInput
    expect: CaseExpect
    attack_type: str | None = None
    attacked_field: str | None = None
    canary: str | None = None

    @property
    def is_attack(self) -> bool:
        return self.category in ATTACK_CATEGORIES

    @model_validator(mode="after")
    def _attack_fields_match_category(self) -> Case:
        fields = (self.attack_type, self.attacked_field, self.canary)
        if self.is_attack and not all(fields):
            raise ValueError(f"{self.id}: attack cases need attack_type, attacked_field, canary")
        if not self.is_attack and any(fields):
            raise ValueError(f"{self.id}: only attack cases may carry attack fields")
        return self


@dataclass(frozen=True)
class EvalOrg:
    """Stand-in for the ORM Organization with the four fields `_build_prompt` reads.

    Not an ORM instance, so the harness needs no mapper setup and has no path
    to a database session. A new attribute read in `_build_prompt` fails loudly.
    """

    name: str | None
    industry_label: str | None
    employee_range: str | None
    primary_state: str | None


@dataclass(frozen=True)
class Dataset:
    path: Path
    version: str
    manifest_hash: str
    cases: list[Case]

    def select(self, split: str) -> list[Case]:
        if split == "all":
            return list(self.cases)
        return [c for c in self.cases if c.split == split]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(cases: list[Case]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for (split, category), n in sorted(Counter((c.split, c.category) for c in cases).items()):
        out.setdefault(split, {})[category] = n
    return out


def _parse_cases(path: Path) -> list[Case]:
    cases = [
        Case.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dupes = [cid for cid, n in Counter(c.id for c in cases).items() if n > 1]
    if dupes:
        raise ValueError(f"duplicate case ids: {sorted(dupes)}")
    return cases


def write_manifest(
    dataset_dir: Path,
    *,
    version: str,
    date: str,
    generator: str | None = None,
    seed: int | None = None,
    generator_sha256: str | None = None,
) -> Path:
    """Write MANIFEST.json for the files currently in `dataset_dir`.

    `generator_sha256` is recorded only when given (generated versions).
    """
    dataset_dir = Path(dataset_dir)
    cases = _parse_cases(dataset_dir / CASES_FILE)
    files = {
        p.name: _sha256(p)
        for p in sorted(dataset_dir.iterdir())
        if p.is_file() and p.name != MANIFEST_FILE
    }
    attack_cases: dict[str, dict[str, str]] = {}
    for c in cases:
        if c.is_attack:
            attack_cases.setdefault(c.split, {})[c.id] = c.attack_type or ""
    manifest = {
        "version": version,
        "date": date,
        "files": files,
        "counts": _counts(cases),
        "attack_cases": attack_cases,
        "generator": generator,
        "seed": seed,
    }
    if generator_sha256 is not None:
        manifest["generator_sha256"] = generator_sha256
    path = dataset_dir / MANIFEST_FILE
    # LF on every OS, so the manifest hash matches across checkouts.
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def manifest_hash(dataset_dir: Path) -> str:
    return _sha256(Path(dataset_dir) / MANIFEST_FILE)


def load_dataset(dataset_dir: Path) -> Dataset:
    """Load a dataset, refusing it if any file or count disagrees with the manifest."""
    dataset_dir = Path(dataset_dir)
    manifest = json.loads((dataset_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    if CASES_FILE not in files:
        raise ManifestMismatchError(f"{MANIFEST_FILE} does not list {CASES_FILE}")
    for name, expected in sorted(files.items()):
        path = dataset_dir / name
        if not path.is_file() or _sha256(path) != expected:
            raise ManifestMismatchError(f"{name} does not match its manifest hash")
    cases = _parse_cases(dataset_dir / CASES_FILE)
    if _counts(cases) != manifest.get("counts"):
        raise ManifestMismatchError("case counts do not match the manifest counts")
    return Dataset(
        path=dataset_dir,
        version=str(manifest["version"]),
        manifest_hash=manifest_hash(dataset_dir),
        cases=cases,
    )


def resolve_dataset(name_or_path: str) -> Path:
    """A bare version name maps to dataset/<name>; anything else is a path."""
    candidate = DATASET_ROOT / name_or_path
    if "/" not in name_or_path and "\\" not in name_or_path and candidate.is_dir():
        return candidate
    return Path(name_or_path)


def _engine_order(findings: list[Finding]) -> list[Finding]:
    """FindingsEngine.build's sort (findings_engine.py:1589); stable, so ties keep input order."""
    return sorted(findings, key=lambda f: -(f.severity_score or _severity_score(f.severity, 0.5)))


def kev_finding_ids(findings: list[Finding]) -> list[str]:
    """R1: the top-3 KEV findings by severity_score (all of them if fewer).

    Ranked over the findings the prompt actually shows: the engine's order,
    capped like `_build_prompt`. Stage B must avoid ties at the third slot.
    """
    shown = _engine_order(findings)[:PROMPT_FINDINGS_CAP]
    kev = [f for f in shown if f.source == KEV_SOURCE and f.severity in KEV_SEVERITIES]
    return [f.id for f in kev[:KEV_TOP_N]]


def build_inputs(case: Case) -> tuple[EvalOrg, FindingsReport, float]:
    """Build the org, FindingsReport and risk score exactly as production would.

    Mirrors FindingsEngine.build (sort by severity_score, _build_summary) and
    AISummaryService.build (calculate_smb_risk_score), with no database.
    """
    o = case.input.org
    org = EvalOrg(
        name=o.name,
        industry_label=o.industry_label,
        employee_range=o.employee_range,
        primary_state=o.primary_state,
    )
    findings = _engine_order(case.input.findings)
    report = FindingsReport(
        org_id=0,
        findings=findings,
        summary=_build_summary(findings),
        generated_at=_GENERATED_AT,
        data_sources_used=sorted({f.source for f in findings}),
        assessment_tier=case.input.assessment_tier,
    )
    risk_score = calculate_smb_risk_score(o.industry_label, o.employee_range).score
    return org, report, risk_score
