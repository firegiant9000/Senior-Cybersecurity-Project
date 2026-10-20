"""Pinned model settings for the AI summary eval (protocol §1).

Every key is required and unknown keys are rejected, so a typo can never
silently fall back to a vendor default.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = HERE / "eval_config.yaml"


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: str = Field(min_length=1)
    sdk_target: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    top_k: int = Field(ge=1)
    candidate_count: int = Field(ge=1, le=1)
    seed: int
    # Caps response and thinking tokens together (Gemini 3.x docs).
    max_output_tokens: int = Field(ge=1)
    # Gemini 3.x thinking can't be turned off; "minimal" is the lowest level.
    thinking_level: Literal["minimal", "low", "medium", "high"]
    # Milliseconds: google-genai's HttpOptions.timeout unit. The floor catches a
    # value written in seconds.
    timeout_ms: int = Field(ge=1000)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_yaml_mapping(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{Path(path).name} must be a YAML mapping")
    return data


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> EvalConfig:
    return EvalConfig.model_validate(load_yaml_mapping(path))
