"""The eval runner: guards, spend caps, logs and key hygiene (protocol §3, §6).

No test here touches the network or a real key: dry runs use the built-in fake
client, and "real" runs monkeypatch ai_summary._call_gemini_raw.
"""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import ai_summary
from evals.ai_summary import run_eval
from evals.ai_summary.run_eval import (
    BACKEND_DIR,
    INDEX_FIELDS,
    RESPONSE_FIELDS,
    RUN_META_FIELDS,
    heldout_allowed,
    main,
)
from tests.evals.helpers import attack_case, case, write_dataset

SENTINEL = "AIzaSySENTINEL-must-never-be-written-0123456789"

_CONFIG = """\
model: gemini-2.5-flash
sdk_target: google-genai
temperature: 0
top_p: 0.95
top_k: 40
candidate_count: 1
seed: 1
max_output_tokens: 1000
thinking_budget: 0
timeout_ms: 20000
"""

# Input is free, output costs $1 per 1M tokens: every call is estimated at
# exactly max_output_tokens (1000) x $1/1M = $0.001, whatever the prompt length.
_PRICING = """\
model: gemini-2.5-flash
currency: USD
verified: {verified}
checked_on: 2026-10-20
source_url: https://example.com/pricing
input_per_1m_tokens: 0
output_per_1m_tokens: 1.0
"""

_VALID_JSON = json.dumps(
    {
        "narrative": "n",
        "posture_statement": "p",
        "notable_risks": [],
        "data_gaps": [],
        "next_steps": [],
    }
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    datasets = tmp_path / "datasets"
    ds = write_dataset(
        datasets,
        [
            case("dev-1"),
            case("dev-2"),
            attack_case("dev-3", "CANARY-TEST-0001"),
            case("ho-1", split="heldout"),
        ],
    )
    config = tmp_path / "eval_config.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    pricing = tmp_path / "pricing.yaml"
    pricing.write_text(_PRICING.format(verified="true"), encoding="utf-8")
    unverified = tmp_path / "pricing-unverified.yaml"
    unverified.write_text(_PRICING.format(verified="false"), encoding="utf-8")
    env_file = tmp_path / ".env.local"
    env_file.write_text(f"GEMINI_API_KEY={SENTINEL}\n", encoding="utf-8")
    return SimpleNamespace(
        tmp=tmp_path,
        dataset=ds,
        config=config,
        pricing=pricing,
        unverified=unverified,
        env_file=env_file,
        runs=tmp_path / "runs",
    )


def _args(env, run_id="D1-test", *, split="dev", repeats=1, max_calls=50, spend="1", extra=()):
    return [
        "--run-id",
        run_id,
        "--split",
        split,
        "--repeats",
        str(repeats),
        "--max-calls",
        str(max_calls),
        "--max-spend-usd",
        spend,
        "--pricing",
        str(env.pricing),
        "--dataset",
        str(env.dataset),
        "--config",
        str(env.config),
        "--runs-dir",
        str(env.runs),
        "--env-file",
        str(env.env_file),
        *extra,
    ]


def _fake_response(text=_VALID_JSON, candidates=1000):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        usage_metadata=SimpleNamespace(
            prompt_token_count=1500,
            candidates_token_count=candidates,
            thoughts_token_count=None,
            total_token_count=1500 + candidates,
        ),
        model_version="gemini-2.5-flash-test",
    )


@pytest.fixture
def fake_gemini(monkeypatch):
    calls: list[str] = []

    def _raw(prompt):
        calls.append(prompt)
        return _fake_response()

    monkeypatch.setattr(ai_summary, "_call_gemini_raw", _raw)
    return calls


def _lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ── held-out guard ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("run_id", "allowed"),
    [
        ("B0-20261020", True),
        ("B1-20261021", True),
        ("F-20261101", True),
        ("B0-DRY", True),
        ("F", True),
        ("D1-20261025", False),
        ("DRY1", False),
        ("FOO", False),
        ("B10-x", False),
        ("b0-lowercase", False),
    ],
)
def test_heldout_allowed(run_id, allowed):
    assert heldout_allowed(run_id) is allowed


@pytest.mark.parametrize("split", ["heldout", "all"])
def test_heldout_guard_refuses_dev_run_ids(env, fake_gemini, capsys, split):
    code = main(_args(env, "D1-test", split=split))
    assert code == 2
    assert "held-out" in capsys.readouterr().err
    assert not env.runs.exists()
    assert fake_gemini == []


def test_heldout_allowed_for_b0(env, fake_gemini):
    assert main(_args(env, "B0-20261020", split="heldout")) == 0
    rows = _lines(env.runs / "B0-20261020" / "responses.jsonl")
    assert [r["case_id"] for r in rows] == ["ho-1"]


# ── spend guard ────────────────────────────────────────────────────────────


def test_max_calls_aborts_before_the_next_call(env, fake_gemini):
    code = main(_args(env, max_calls=2))
    assert code == 3
    assert len(fake_gemini) == 2
    meta = json.loads((env.runs / "D1-test" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "aborted_max_calls"
    assert meta["calls_made"] == 2
    assert len(_lines(env.runs / "D1-test" / "responses.jsonl")) == 2


def test_spend_cap_aborts_before_the_call_that_would_exceed_it(env, fake_gemini):
    # $0.001 per call: calls 1 and 2 fit in $0.0025, call 3 would reach $0.003.
    code = main(_args(env, spend="0.0025"))
    assert code == 3
    assert len(fake_gemini) == 2
    meta = json.loads((env.runs / "D1-test" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "aborted_spend_cap"
    assert meta["spend_usd"] == pytest.approx(0.002)


def test_spend_cap_below_one_call_makes_no_call(env, fake_gemini):
    assert main(_args(env, spend="0.0005")) == 3
    assert fake_gemini == []


def test_spend_tally_uses_actual_cost_when_it_exceeds_the_estimate(env, monkeypatch):
    # Thinking or a missing output cap can make a call cost more than estimated;
    # the tally must use the real usage so the next call is refused.
    calls: list[str] = []

    def _raw(prompt):
        calls.append(prompt)
        return _fake_response(candidates=2000)  # $0.002 actual vs $0.001 estimated

    monkeypatch.setattr(ai_summary, "_call_gemini_raw", _raw)
    assert main(_args(env, spend="0.0025")) == 3
    assert len(calls) == 1


def test_each_response_line_is_on_disk_with_its_cost(env, fake_gemini):
    main(_args(env, max_calls=2))
    rows = _lines(env.runs / "D1-test" / "responses.jsonl")
    assert [r["cost_usd"] for r in rows] == [pytest.approx(0.001)] * 2


# ── logged fields ──────────────────────────────────────────────────────────


def test_dry_run_is_offline_and_writes_every_field(env, monkeypatch, capsys):
    def _no_network(*_a, **_k):
        raise AssertionError("dry run touched the network")

    def _no_sdk(_prompt):
        raise AssertionError("dry run called the SDK")

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(ai_summary, "_call_gemini_raw", _no_sdk)
    env.env_file.unlink()  # no key anywhere

    code = main(_args(env, "DRY1", repeats=2, extra=["--dry-run"]))
    assert code == 0, capsys.readouterr().err

    run_dir = env.runs / "_dry" / "DRY1"
    rows = _lines(run_dir / "responses.jsonl")
    assert len(rows) == 3 * 2
    for row in rows:
        assert set(row) == set(RESPONSE_FIELDS)
        assert row["parse_ok"] is True
        assert row["error_class"] is None
        assert len(row["request_hash"]) == 64
    assert [r["repeat"] for r in rows] == [1, 1, 1, 2, 2, 2]

    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert set(RUN_META_FIELDS) <= set(meta)
    assert meta["dry_run"] is True
    assert meta["status"] == "completed"
    assert meta["sdk_name"] == "dry-run-fake"
    assert meta["dataset_version"] == "t1"
    assert len(meta["prompt_template_sha256"]) == 64

    index = _lines(env.runs / "_dry" / "index.jsonl")
    assert len(index) == 1
    assert set(index[0]) == set(INDEX_FIELDS)
    assert not (env.runs / "index.jsonl").exists()


def test_cli_dry_run_in_a_fresh_process(env):
    # A fresh interpreter has none of the app imports the test session has,
    # and neither a key nor DATABASE_URL in its environment.
    clean_env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "DATABASE_URL")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.ai_summary.run_eval",
            *_args(env, "DRY-CLI", extra=["--dry-run"]),
        ],
        cwd=BACKEND_DIR,
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (env.runs / "_dry" / "DRY-CLI" / "responses.jsonl").exists()


def test_real_run_logs_sdk_fields(env, fake_gemini):
    assert main(_args(env)) == 0
    row = _lines(env.runs / "D1-test" / "responses.jsonl")[0]
    assert row["finish_reason"] == "STOP"
    assert row["model_version"] == "gemini-2.5-flash-test"
    assert row["usage_metadata"] == {
        "prompt_token_count": 1500,
        "candidates_token_count": 1000,
        "thoughts_token_count": None,
        "total_token_count": 2500,
    }
    meta = json.loads((env.runs / "D1-test" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["sdk_name"] == "google-generativeai"
    assert meta["dry_run"] is False
    assert len(_lines(env.runs / "index.jsonl")) == 1


def test_prompt_is_the_production_prompt(env, fake_gemini):
    main(_args(env, max_calls=1))
    assert "Example Bakery LLC" in fake_gemini[0]
    assert "RESPONSE FORMAT:" in fake_gemini[0]


def test_unparseable_output_is_recorded_not_repaired(env, monkeypatch):
    monkeypatch.setattr(
        ai_summary, "_call_gemini_raw", lambda _p: _fake_response(text="```json\n{}\n```")
    )
    main(_args(env, max_calls=1))
    row = _lines(env.runs / "D1-test" / "responses.jsonl")[0]
    assert row["raw_text"] == "```json\n{}\n```"
    assert row["parse_ok"] is False
    assert row["parse_error_class"] == "ValidationError"


# ── key hygiene ────────────────────────────────────────────────────────────


def test_sentinel_key_never_written_or_printed(env, monkeypatch, capsys):
    seen_keys: list[str] = []

    def _raw(prompt):
        seen_keys.append(ai_summary.settings.GEMINI_API_KEY)
        if len(seen_keys) == 1:
            # SDK errors can embed the request URL, key included.
            raise RuntimeError(
                "403 POST https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash:generateContent?key={SENTINEL} x-goog-api-key: {SENTINEL}"
            )
        return _fake_response()

    monkeypatch.setattr(ai_summary, "_call_gemini_raw", _raw)
    before = ai_summary.settings.GEMINI_API_KEY

    assert main(_args(env)) == 0
    from evals.ai_summary import score

    assert score.main(["--run-id", "D1-test", "--runs-dir", str(env.runs)]) == 0

    assert seen_keys and all(k == SENTINEL for k in seen_keys)  # the key did flow
    assert ai_summary.settings.GEMINI_API_KEY == before  # and was restored
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out
    assert SENTINEL not in captured.err
    written = [p for p in env.runs.rglob("*") if p.is_file()]
    assert {p.name for p in written} >= {
        "responses.jsonl",
        "run_meta.json",
        "index.jsonl",
        "scores.json",
        "manual_judgement.csv",
    }
    for path in written:
        assert SENTINEL.encode() not in path.read_bytes(), path.name
    error_row = _lines(env.runs / "D1-test" / "responses.jsonl")[0]
    assert error_row["error_class"] == "RuntimeError"
    assert "googleapis" not in json.dumps(error_row)


def test_missing_key_says_only_key_not_set(env, fake_gemini, capsys):
    env.env_file.write_text("OTHER=1\n", encoding="utf-8")
    assert main(_args(env)) == 2
    assert capsys.readouterr().err.strip() == "key not set"
    assert not env.runs.exists()
    assert fake_gemini == []


def test_key_comes_from_env_file_not_process_env(env, fake_gemini, monkeypatch, capsys):
    env.env_file.unlink()
    monkeypatch.setenv("GEMINI_API_KEY", "from-process-env")
    assert main(_args(env)) == 2
    assert capsys.readouterr().err.strip() == "key not set"


# ── other refusals ─────────────────────────────────────────────────────────


def test_real_run_refuses_unverified_pricing(env, fake_gemini, capsys):
    args = _args(env)
    args[args.index("--pricing") + 1] = str(env.unverified)
    assert main(args) == 2
    assert "unverified" in capsys.readouterr().err
    assert fake_gemini == []


def test_dry_run_accepts_unverified_pricing(env):
    args = _args(env, "DRY2", extra=["--dry-run"])
    args[args.index("--pricing") + 1] = str(env.unverified)
    assert main(args) == 0


def test_refuses_to_reuse_a_run_id(env, fake_gemini, capsys):
    assert main(_args(env)) == 0
    assert main(_args(env)) == 2
    assert "exists" in capsys.readouterr().err


def test_refuses_path_like_run_id(env, fake_gemini, capsys):
    assert main(_args(env, "../escape")) == 2
    assert not (env.tmp / "escape").exists()


def test_reported_runs_refuse_the_fixture_dataset(env, fake_gemini, capsys):
    args = _args(env, "B1-20261021")
    args[args.index("--dataset") + 1] = "fixture"
    assert main(args) == 2
    assert "fixture" in capsys.readouterr().err


def test_refuses_when_production_model_differs_from_config(env, fake_gemini, monkeypatch):
    monkeypatch.setattr(ai_summary.settings, "GEMINI_MODEL", "gemini-1.5-flash")
    assert main(_args(env)) == 2
    assert fake_gemini == []


def test_runner_never_constructs_the_db_service(env, fake_gemini, monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("harness must bypass AISummaryService and its DB fallback")

    monkeypatch.setattr(run_eval.ai_summary.AISummaryService, "__init__", _boom)
    assert main(_args(env)) == 0
