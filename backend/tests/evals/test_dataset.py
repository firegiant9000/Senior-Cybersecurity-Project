"""Dataset loading, manifest checks and input building (protocol §2)."""

import json

import pytest
from pydantic import ValidationError

from app.schemas.findings import Finding
from app.services.risk_scoring import calculate_smb_risk_score
from evals.ai_summary.dataset import (
    FIXTURE_DATASET,
    Case,
    ManifestMismatchError,
    build_inputs,
    kev_finding_ids,
    load_dataset,
)
from tests.evals.helpers import attack_case, case, finding, write_dataset


def test_loads_cases_and_manifest_hash(tmp_path):
    ds = write_dataset(tmp_path, [case("dev-1"), case("ho-1", split="heldout")])
    loaded = load_dataset(ds)
    assert [c.id for c in loaded.cases] == ["dev-1", "ho-1"]
    assert loaded.version == "t1"
    assert len(loaded.manifest_hash) == 64
    assert isinstance(loaded.cases[0].input.findings[0], Finding)


def test_split_selection(tmp_path):
    ds = write_dataset(tmp_path, [case("dev-1"), case("ho-1", split="heldout")])
    loaded = load_dataset(ds)
    assert [c.id for c in loaded.select("dev")] == ["dev-1"]
    assert [c.id for c in loaded.select("heldout")] == ["ho-1"]
    assert [c.id for c in loaded.select("all")] == ["dev-1", "ho-1"]


def test_manifest_is_written_with_lf_endings(tmp_path):
    # The manifest hash must be the same on Windows and Linux checkouts.
    ds = write_dataset(tmp_path, [case("dev-1")])
    assert b"\r\n" not in (ds / "MANIFEST.json").read_bytes()


def test_refuses_one_byte_edit_to_cases(tmp_path):
    ds = write_dataset(tmp_path, [case("dev-1")])
    path = ds / "cases.jsonl"
    data = path.read_bytes()
    path.write_bytes(data.replace(b"Example Bakery", b"Example Bakerz"))
    with pytest.raises(ManifestMismatchError, match="cases.jsonl"):
        load_dataset(ds)


def test_refuses_counts_that_disagree_with_manifest(tmp_path):
    ds = write_dataset(tmp_path, [case("dev-1")])
    manifest = json.loads((ds / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["counts"]["dev"]["normal"] = 2
    (ds / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestMismatchError, match="counts"):
        load_dataset(ds)


def test_refuses_duplicate_case_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(write_dataset(tmp_path, [case("dev-1"), case("dev-1")]))


def test_attack_case_needs_type_field_and_canary():
    bad = case("dev-a", category="org_injection")
    with pytest.raises(ValidationError):
        Case.model_validate(bad)


def test_normal_case_must_not_carry_attack_fields():
    bad = case("dev-n", attack={"canary": "CANARY-X"})
    with pytest.raises(ValidationError):
        Case.model_validate(bad)


def test_attack_case_validates():
    parsed = Case.model_validate(attack_case("dev-a", "CANARY-7F3A"))
    assert parsed.canary == "CANARY-7F3A"
    assert parsed.is_attack


def test_kev_ids_follow_r1_definition():
    findings = [
        Finding.model_validate(f)
        for f in [
            finding("crit", severity="critical", score=95),
            finding("high1", severity="high", score=72),
            finding("high2", severity="high", score=65),
            finding("high3", severity="high", score=61),
            finding("medium-kev", severity="medium", score=50),
            finding("not-kev", severity="critical", score=99, source="ic3_sector_weights"),
        ]
    ]
    assert kev_finding_ids(findings) == ["crit", "high1", "high2"]


def test_build_inputs_matches_production_shapes(tmp_path):
    findings = [
        finding("low", severity="low", score=25, source="assessment_readiness"),
        finding("crit", severity="critical", score=90),
    ]
    parsed = Case.model_validate(case("dev-1", findings=findings))
    org, report, risk_score = build_inputs(parsed)

    assert org.name == "Example Bakery LLC"
    assert org.primary_state == "OH"
    # The engine sorts by severity_score, highest first.
    assert [f.id for f in report.findings] == ["crit", "low"]
    assert report.summary.total == 2
    assert report.summary.by_severity == {"critical": 1, "low": 1}
    assert report.assessment_tier == "partial"
    expected = calculate_smb_risk_score("Retail Trade", "1-10").score
    assert risk_score == expected


def test_committed_fixture_dataset_verifies():
    loaded = load_dataset(FIXTURE_DATASET)
    assert loaded.version == "fixture"
    assert loaded.select("dev")
    for c in loaded.cases:
        assert c.expect.kev_ids_required == kev_finding_ids(c.input.findings)
        assert c.expect.allowed_citation_ids == [f.id for f in c.input.findings]
