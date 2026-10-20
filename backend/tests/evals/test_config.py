"""The pinned eval settings loader (protocol §1)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.ai_summary.config import DEFAULT_CONFIG_PATH, EvalConfig, file_sha256, load_config

_VALID = """\
model: gemini-3.6-flash
sdk_target: google-genai
temperature: 0
top_p: 0.95
top_k: 40
candidate_count: 1
seed: 1
max_output_tokens: 2048
thinking_level: minimal
timeout_ms: 20000
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "eval_config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_committed_config_has_protocol_values():
    cfg = load_config(DEFAULT_CONFIG_PATH)
    assert cfg.model == "gemini-3.6-flash"
    assert cfg.sdk_target == "google-genai"
    assert cfg.temperature == 0
    assert cfg.candidate_count == 1
    assert cfg.thinking_level == "minimal"
    assert cfg.timeout_ms == 20000


def test_loads_valid_config(tmp_path):
    cfg = load_config(_write(tmp_path, _VALID))
    assert isinstance(cfg, EvalConfig)
    assert cfg.top_k == 40


@pytest.mark.parametrize(
    "key",
    [
        "model",
        "sdk_target",
        "temperature",
        "top_p",
        "top_k",
        "candidate_count",
        "seed",
        "max_output_tokens",
        "thinking_level",
        "timeout_ms",
    ],
)
def test_rejects_missing_key(tmp_path, key):
    text = "\n".join(line for line in _VALID.splitlines() if not line.startswith(f"{key}:"))
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, text))


@pytest.mark.parametrize("level", ["off", "none", "0", "MINIMAL"])
def test_rejects_unknown_thinking_level(tmp_path, level):
    # Gemini 3.x thinking can't be turned off; only the documented levels pass.
    text = _VALID.replace("thinking_level: minimal", f"thinking_level: {level}")
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, text))


def test_rejects_legacy_thinking_budget(tmp_path):
    # 2026-10-20 amendment: thinking_budget pinned gemini-2.5-flash; 3.x uses levels.
    text = _VALID.replace("thinking_level: minimal", "thinking_budget: 0")
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, text))


def test_rejects_unknown_key(tmp_path):
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, _VALID + "temprature: 1\n"))


def test_rejects_non_mapping(tmp_path):
    with pytest.raises(ValueError, match="mapping"):
        load_config(_write(tmp_path, "- just\n- a list\n"))


def test_rejects_timeout_in_seconds(tmp_path):
    # google-genai's HttpOptions.timeout is milliseconds; 20 would be 20 ms.
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, _VALID.replace("timeout_ms: 20000", "timeout_ms: 20")))


def test_file_sha256_changes_with_content(tmp_path):
    a = file_sha256(_write(tmp_path, _VALID))
    b = file_sha256(_write(tmp_path, _VALID.replace("seed: 1", "seed: 2")))
    assert a != b
    assert len(a) == 64
