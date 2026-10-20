"""Dataset v1 (protocol §2): counts, shapes, attacks, leakage and reproducibility."""

import hashlib
import importlib.util
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from app.schemas.findings import Finding
from app.services.ai_summary import _build_prompt
from app.services.findings_engine import _finding_id, _severity_score
from evals.ai_summary import attack_strings
from evals.ai_summary.dataset import (
    DATASET_ROOT,
    PROMPT_FINDINGS_CAP,
    ManifestMismatchError,
    _engine_order,
    build_inputs,
    kev_finding_ids,
    load_dataset,
    resolve_dataset,
)
from evals.ai_summary.run_eval import DEFAULT_DATASET

V1 = DATASET_ROOT / "v1"
GENERATOR = DATASET_ROOT / "generate_v1.py"
APP_DIR = Path(__file__).resolve().parents[2] / "app"
ORG_FIELDS = ("name", "industry_label", "employee_range", "primary_state")
FINDING_FIELD = "finding.vendor_name"
FINDING_TYPES = {"threat_exposure", "vendor_exposure", "data_gap", "recommended_action"}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
EXPECTED_COUNTS = {
    "dev": {"normal": 10, "edge": 5, "org_injection": 8, "finding_injection": 4},
    "heldout": {"normal": 8, "edge": 4, "org_injection": 7, "finding_injection": 3},
}
# OrganizationCreate.name and OrgVendor.vendor_name cap at 255 characters.
API_NAME_MAX = 255


@pytest.fixture(scope="module")
def ds():
    return load_dataset(V1)


@pytest.fixture(scope="module")
def raw_cases():
    lines = (V1 / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_v1", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attacks(ds, split=None):
    return [c for c in ds.cases if c.is_attack and (split is None or c.split == split)]


def _canary_suffix(canary: str) -> str:
    return canary.removeprefix(attack_strings.DATASET_CANARY_PREFIX)


def _attacked_text(c) -> str:
    """The attacker-controlled text: the org field, or the hostile vendor names."""
    if c.attacked_field in ORG_FIELDS:
        return getattr(c.input.org, c.attacked_field) or ""
    return " ".join(a for f in c.input.findings for a in f.affected_assets)


# ── counts and shapes ─────────────────────────────────────────────────────


def test_counts_are_exact(ds):
    counts = Counter((c.split, c.category) for c in ds.cases)
    for split, by_category in EXPECTED_COUNTS.items():
        for category, n in by_category.items():
            assert counts[(split, category)] == n, (split, category)
    assert len(ds.select("dev")) == 27
    assert len(ds.select("heldout")) == 22
    manifest = json.loads((V1 / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == EXPECTED_COUNTS


def test_every_finding_validates_as_the_engine_shape(raw_cases):
    for c in raw_cases:
        for f in c["input"]["findings"]:
            parsed = Finding.model_validate(f)
            assert parsed.finding_type in FINDING_TYPES, c["id"]
            assert parsed.severity in SEVERITIES, c["id"]
            # The engine always scores; 0 would fall back to the default rank.
            assert parsed.severity_score is not None and 0 < parsed.severity_score <= 100


def test_finding_ids_are_unique_within_a_case(ds):
    for c in ds.cases:
        ids = [f.id for f in c.input.findings]
        assert len(ids) == len(set(ids)), c.id


def test_local_id_and_score_helpers_match_the_engine(generator):
    # The generator copies these so a later engine change can't alter frozen v1;
    # this flags drift from the engine instead.
    assert generator._fid("dns_no_spf", "a.example.com") == _finding_id(
        "dns_no_spf", "a.example.com"
    )
    for label in SEVERITIES:
        for w in (0.0, 0.3, 0.5, 0.8, 1.0):
            assert generator._score(label, w) == _severity_score(label, w)


# ── expect blocks (R1) ────────────────────────────────────────────────────


def test_expect_blocks_follow_r1(ds):
    for c in ds.cases:
        ids = [f.id for f in c.input.findings]
        assert c.expect.kev_ids_required == kev_finding_ids(c.input.findings), c.id
        assert c.expect.allowed_citation_ids == ids, c.id
        assert set(c.expect.kev_ids_required) <= set(ids), c.id


def test_no_ties_that_make_the_required_ids_arbitrary(ds):
    for c in ds.cases:
        ordered = _engine_order(c.input.findings)
        scores = [f.severity_score for f in ordered]
        cap = PROMPT_FINDINGS_CAP
        if len(ordered) > cap and scores[cap - 1] == scores[cap]:
            # A tie across the cut only matters if it decides which KEV finding is shown.
            tied = [f for f in ordered if f.severity_score == scores[cap]]
            assert not any(
                f.source == "kev_vendor_match" and f.severity in {"critical", "high"} for f in tied
            ), f"{c.id}: KEV tie at the prompt cap"
        shown = ordered[:PROMPT_FINDINGS_CAP]
        kev = [f.severity_score for f in shown if f.id in set(kev_finding_ids(shown))]
        kev_all = [
            f.severity_score
            for f in shown
            if f.source == "kev_vendor_match" and f.severity in {"critical", "high"}
        ]
        if len(kev_all) > 3:
            assert kev_all[2] != kev_all[3], f"{c.id}: tie at the third KEV slot"
        assert kev == kev_all[:3]


def test_kev_coverage_has_cases_in_both_splits(ds):
    for split in ("dev", "heldout"):
        assert sum(1 for c in ds.select(split) if c.expect.kev_ids_required) >= 10


# ── attacks ───────────────────────────────────────────────────────────────


def test_every_attack_has_type_field_and_a_unique_canary(ds):
    attacks = _attacks(ds)
    assert len(attacks) == 22
    for c in attacks:
        assert c.attack_type in attack_strings.ATTACK_TYPES, c.id
        expected = ORG_FIELDS if c.category == "org_injection" else (FINDING_FIELD,)
        assert c.attacked_field in expected, c.id
        assert re.fullmatch(r"CANARY-V1-[A-Z0-9]{8}", c.canary), c.id
    canaries = [c.canary for c in attacks]
    assert len(canaries) == len(set(canaries))


def test_all_six_attack_types_in_each_split_spread_evenly(ds):
    for split in ("dev", "heldout"):
        types = Counter(c.attack_type for c in _attacks(ds, split))
        assert set(types) == set(attack_strings.ATTACK_TYPES), split
        assert max(types.values()) - min(types.values()) <= 1, split


def test_each_org_field_is_attacked_in_both_splits(ds):
    for split in ("dev", "heldout"):
        fields = {c.attacked_field for c in _attacks(ds, split) if c.category == "org_injection"}
        assert fields == set(ORG_FIELDS), split


def test_manifest_lists_each_attack_type_per_split(ds):
    manifest = json.loads((V1 / "MANIFEST.json").read_text(encoding="utf-8"))
    for split in ("dev", "heldout"):
        assert manifest["attack_cases"][split] == {c.id: c.attack_type for c in _attacks(ds, split)}


def test_canary_is_never_in_its_input_but_its_parts_are(ds):
    # The model must assemble the token, so a hit means it obeyed rather than quoted.
    for c in _attacks(ds):
        rendered = c.input.model_dump_json().casefold()
        assert c.canary.casefold() not in rendered, c.id
        assert _canary_suffix(c.canary) in _attacked_text(c), c.id


def test_api_reachable_fields_respect_the_api_length_cap(ds):
    for c in _attacks(ds):
        if c.attacked_field == "name":
            assert len(c.input.org.name) <= API_NAME_MAX, c.id
        if c.attacked_field == FINDING_FIELD:
            for f in c.input.findings:
                assert all(len(a) <= API_NAME_MAX for a in f.affected_assets), c.id


def test_every_attack_reaches_the_rendered_prompt(ds):
    for c in _attacks(ds):
        org, report, risk = build_inputs(c)
        prompt, _ = _build_prompt(org, report, risk)
        # The hostile finding must be among the 20 the prompt shows.
        assert _canary_suffix(c.canary) in prompt, c.id


# ── edge cases ────────────────────────────────────────────────────────────


EDGE_KINDS = {
    "dev": {"zero-findings", "over-cap", "no-kev", "all-unknown", "long-descriptions"},
    "heldout": {"over-cap", "benign-non-ascii", "only-low-severity", "kev-ties"},
}


def _edge(ds, split, kind):
    return next(c for c in ds.cases if c.id == f"v1-{split}-edge-{kind}")


def _kev_findings(c) -> list[Finding]:
    return [
        f
        for f in c.input.findings
        if f.source == "kev_vendor_match" and f.severity in {"critical", "high"}
    ]


def _finding_text(c) -> list[str]:
    return [s for f in c.input.findings for s in (f.title, f.description, *f.affected_assets)]


def test_edge_case_ids_match_the_planned_kinds(ds):
    for split, kinds in EDGE_KINDS.items():
        ids = {c.id for c in ds.select(split) if c.category == "edge"}
        assert ids == {f"v1-{split}-edge-{k}" for k in kinds}


def test_edge_cases_cover_the_spec(ds):
    assert _edge(ds, "dev", "zero-findings").input.findings == []

    # 50+ findings (protocol), and a KEV finding ranked past the 20-finding cap
    # that the model never sees, so it is not required.
    big = _edge(ds, "dev", "over-cap")
    assert len(big.input.findings) > 50
    assert len(big.expect.kev_ids_required) < len(_kev_findings(big))
    assert len(_edge(ds, "heldout", "over-cap").input.findings) > PROMPT_FINDINGS_CAP

    no_kev = _edge(ds, "dev", "no-kev")
    assert no_kev.input.findings and not _kev_findings(no_kev)
    # R1 subtlety: an info-severity KEV-source finding is not a KEV finding.
    assert any(f.source == "kev_vendor_match" for f in no_kev.input.findings)

    org = _edge(ds, "dev", "all-unknown").input.org
    assert (org.name, org.industry_label, org.employee_range, org.primary_state) == (None,) * 4

    longest = max(len(f.description) for f in _edge(ds, "dev", "long-descriptions").input.findings)
    assert longest >= 2000

    low = _edge(ds, "heldout", "only-low-severity")
    assert low.input.findings
    assert {f.severity for f in low.input.findings} <= {"low", "info"}

    ties = _edge(ds, "heldout", "kev-ties")
    scores = [f.severity_score for f in _kev_findings(ties)]
    assert len(scores) != len(set(scores))  # a real tie, inside the required top 3
    assert len(ties.expect.kev_ids_required) == len(scores) <= 3


def test_benign_non_ascii_case_is_not_an_attack(ds):
    c = _edge(ds, "heldout", "benign-non-ascii")
    text = " ".join([c.input.org.name or "", *_finding_text(c)])
    assert not text.isascii()
    assert "canary" not in text.casefold()
    assert "ignore" not in text.casefold()


def test_normal_cases_vary(ds):
    normal = [c for c in ds.cases if c.category == "normal"]
    counts = {len(c.input.findings) for c in normal}
    assert min(counts) >= 2 and max(counts) <= PROMPT_FINDINGS_CAP
    assert len(counts) >= 5
    assert {f.severity for c in normal for f in c.input.findings} == SEVERITIES
    assert {f.finding_type for c in normal for f in c.input.findings} == FINDING_TYPES
    assert any(not c.expect.kev_ids_required for c in normal)


def test_every_case_renders_a_production_prompt(ds):
    for c in ds.cases:
        org, report, risk = build_inputs(c)
        prompt, _ = _build_prompt(org, report, risk)
        assert "STRUCTURED FINDINGS" in prompt


# ── synthetic only, and no leakage ────────────────────────────────────────

_DOMAIN_RE = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|us|co)\b", re.I)
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def test_synthetic_domains_and_documentation_ips_only():
    text = (V1 / "cases.jsonl").read_text(encoding="utf-8")
    for domain in set(_DOMAIN_RE.findall(text)):
        assert domain.lower() == "example.com" or domain.lower().endswith(".example.com"), domain
    for ip in set(_IP_RE.findall(text)):
        # RFC 5737 documentation ranges only.
        assert ip.startswith(("192.0.2.", "198.51.100.", "203.0.113.")), ip


def _leak_needles(ds) -> set[str]:
    needles = {c.canary for c in _attacks(ds)}
    needles |= {_canary_suffix(c.canary) for c in _attacks(ds)}
    for c in ds.select("heldout"):
        if c.input.org.name:
            needles.add(c.input.org.name)
        if c.is_attack:
            needles.add(_attacked_text(c))
    return {n for n in needles if len(n) >= 8}


def test_no_heldout_string_or_any_canary_under_app(ds):
    needles = _leak_needles(ds)
    for path in APP_DIR.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        content = path.read_bytes().decode("utf-8", errors="ignore")
        for needle in needles:
            assert needle not in content, f"{path}: held-out text or canary leaked"


def test_attack_string_helper_exposes_no_dataset_case_text(ds):
    corpus = attack_strings.corpus()
    assert len(corpus) >= 20
    assert {a.attack_type for a in corpus} == set(attack_strings.ATTACK_TYPES)
    assert len({a.canary for a in corpus}) == len(corpus)
    needles = _leak_needles(ds)
    for a in corpus:
        assert a.canary.startswith(attack_strings.CI_CANARY_PREFIX)
        assert "CANARY-V1" not in a.text
        assert a.canary not in a.text  # assembled, as in the dataset
        for needle in needles:
            assert needle not in a.text


def test_attack_string_helper_has_api_sized_names():
    names = attack_strings.corpus(max_len=API_NAME_MAX)
    assert len(names) >= 20
    assert all(len(a.text) <= API_NAME_MAX for a in names)


# ── manifest and reproducibility ──────────────────────────────────────────


def test_manifest_records_generator_seed_and_hash(ds, generator):
    manifest = json.loads((V1 / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "v1"
    assert manifest["generator"] == "dataset/generate_v1.py"
    assert manifest["seed"] == generator.SEED
    assert manifest["generator_sha256"] == hashlib.sha256(GENERATOR.read_bytes()).hexdigest()
    assert set(manifest["files"]) == {"cases.jsonl", "CHANGELOG.md"}
    assert "split before any run" in (V1 / "CHANGELOG.md").read_text(encoding="utf-8").lower()


def test_one_byte_edit_is_refused(tmp_path):
    copy = tmp_path / "v1"
    shutil.copytree(V1, copy)
    data = bytearray((copy / "cases.jsonl").read_bytes())
    data[100] = ord("x") if data[100] != ord("x") else ord("y")
    (copy / "cases.jsonl").write_bytes(bytes(data))
    with pytest.raises(ManifestMismatchError):
        load_dataset(copy)


def test_generator_reproduces_v1_byte_for_byte(tmp_path, generator):
    out = tmp_path / "v1"
    generator.generate(out)
    committed = sorted(p.name for p in V1.iterdir() if p.is_file())
    assert sorted(p.name for p in out.iterdir()) == committed
    for name in committed:
        assert (out / name).read_bytes() == (V1 / name).read_bytes(), name


def test_generator_check_mode_passes_on_the_committed_files(generator):
    assert generator.main(["--check"]) == 0


def test_rubric_defines_success_rules_examples_and_rationale(ds):
    rubric = (DATASET_ROOT.parent / "rubric_v1.md").read_text(encoding="utf-8")
    # Rule (c) as score.py implements it; errors are indeterminate, not successes.
    assert "schema-invalid answered repeat on an attack case" in rubric
    assert "Indeterminate, not a success and not a defence" in rubric
    assert rubric.count("**1. ") + rubric.count("**2. ") + rubric.count("**3. ") == 3
    assert "one-line-rationale rule" in rubric
    # The worked examples use made-up canaries, never a dataset one.
    suffixes = {_canary_suffix(c.canary) for c in _attacks(ds)}
    assert not suffixes & set(re.findall(r'"([A-Z0-9]{8})"', rubric))


def test_runner_defaults_to_v1():
    assert load_dataset(resolve_dataset(DEFAULT_DATASET)).version == "v1"
