"""Run the AI summary eval against a versioned dataset (protocol §3, §6).

    python -m evals.ai_summary.run_eval --run-id DRY1 --split dev --repeats 1 \
        --max-calls 5 --max-spend-usd 0.01 \
        --pricing evals/ai_summary/pricing-TEMPLATE.yaml --dry-run

Each call renders the production prompt (`_build_prompt`) and calls the
production SDK seam (`_call_gemini_raw`) directly, so the database last-good
fallback in AISummaryService.build is bypassed and a failed call is scored as
a failure, never as an older output.

Key hygiene: the key is read only from the env file (default backend/.env.local)
and is never printed, logged or written. Errors are recorded by class only,
because SDK error messages can carry the request URL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import dotenv_values

from app.schemas.ai_summary import StructuredSummary
from app.schemas.findings import Finding, FindingsReport
from app.services import ai_summary
from app.services.findings_engine import _build_summary
from evals.ai_summary.config import DEFAULT_CONFIG_PATH, EvalConfig, file_sha256, load_config
from evals.ai_summary.dataset import (
    Dataset,
    EvalOrg,
    build_inputs,
    load_dataset,
    resolve_dataset,
)
from evals.ai_summary.pricing import Pricing, call_cost_usd, load_pricing

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = Path(__file__).resolve().parent / "runs"
DEFAULT_ENV_FILE = BACKEND_DIR / ".env.local"
DRY_SUBDIR = "_dry"
# Reported runs use v1; tests pass the fixture (or a temp dataset) explicitly.
DEFAULT_DATASET = "v1"
FIXTURE_VERSION = "fixture"

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
# Protocol §3: the held-out split runs only in B0, B1 and F.
HELDOUT_RUN_RE = re.compile(r"^(B0|B1|F)(-|$)")
# Import statements only, so comments and strings can't mislabel the SDK.
_OLD_SDK_IMPORT = re.compile(
    r"^\s*(import google\.generativeai\b|from google\.generativeai\b|"
    r"from google import generativeai\b)",
    re.MULTILINE,
)
_NEW_SDK_IMPORT = re.compile(
    r"^\s*(import google\.genai\b|from google\.genai\b|from google import genai\b)",
    re.MULTILINE,
)
# Protocol §3: every case runs 3 times in a reported run.
REPORTED_REPEATS = 3
# Conservative prompt-token estimate: ~4 chars/token for English, 3 leaves
# headroom for injected Unicode, which tokenises worse.
CHARS_PER_TOKEN_ESTIMATE = 3

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_ABORTED = 3

RESPONSE_FIELDS = (
    "request_hash",
    "case_id",
    "split",
    "category",
    "repeat",
    "raw_text",
    "parse_ok",
    "parse_error_class",
    "finish_reason",
    "usage_metadata",
    "thoughts_tokens_derived",
    "latency_ms",
    "model_version",
    "error_class",
    "cost_usd",
    "cost_usd_estimate",
)
RUN_META_FIELDS = (
    "run_id",
    "status",
    "dry_run",
    "split",
    "repeats",
    "date",
    "git_sha",
    "git_dirty",
    "harness_patch_sha",
    "ai_summary_py_sha256",
    "sdk_name",
    "sdk_version",
    "sdk_versions_installed",
    "production_model",
    "config_path",
    "config_hash",
    "config",
    "dataset_version",
    "dataset_path",
    "manifest_hash",
    "prompt_template_sha256",
    "pricing_file",
    "pricing_hash",
    "pricing_verified",
    "max_calls",
    "max_spend_usd",
    "planned_calls",
    "calls_made",
    "spend_usd",
)
INDEX_FIELDS = (
    "run_id",
    "date",
    "split",
    "dry_run",
    "dataset_version",
    "manifest_hash",
    "git_sha",
    "planned_calls",
    "max_calls",
    "max_spend_usd",
)
_USAGE_FIELDS = (
    "prompt_token_count",
    "candidates_token_count",
    "thoughts_token_count",
    "total_token_count",
)


class RefusedError(Exception):
    """A guard refused the run before anything was written."""


# ── guards ────────────────────────────────────────────────────────────────


def heldout_allowed(run_id: str) -> bool:
    return HELDOUT_RUN_RE.match(run_id) is not None


def _load_key(env_file: Path) -> str | None:
    """The key comes only from the env file (R4), never the process env."""
    if not env_file.is_file():
        return None
    value = dotenv_values(env_file).get("GEMINI_API_KEY")
    return value.strip() if value and value.strip() else None


# ── provenance ────────────────────────────────────────────────────────────


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(BACKEND_DIR), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _harness_patch_sha() -> str | None:
    """The commit that introduced the harness seam `_call_gemini_raw`."""
    out = _git(
        "log", "--reverse", "--format=%H", "-S", "def _call_gemini_raw", "--", _ai_summary_path()
    )
    return out.splitlines()[0] if out else None


def _ai_summary_path() -> str:
    return str(Path(inspect.getfile(ai_summary)).resolve())


def _installed(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def _sdk_name_of(obj: Any) -> str:
    """Which SDK the production code imports (lazily, so read the source)."""
    source = inspect.getsource(obj)
    old = _OLD_SDK_IMPORT.search(source) is not None
    new = _NEW_SDK_IMPORT.search(source) is not None
    if old == new:  # neither, or both: don't guess
        return "unknown"
    return "google-generativeai" if old else "google-genai"


def prompt_template_sha256() -> str:
    """SHA-256 of the prompt rendered from a fixed placeholder input.

    Any change to the template text changes this hash; the per-call
    request_hash covers the actual rendered prompts.
    """
    org = EvalOrg(
        name="{org.name}",
        industry_label="{org.industry_label}",
        employee_range="{org.employee_range}",
        primary_state="{org.primary_state}",
    )
    findings = [
        Finding(
            id="{finding.id}",
            finding_type="{finding.finding_type}",
            severity="high",
            severity_score=70.0,
            title="{finding.title}",
            description="{finding.description}",
            evidence={},
            source="{finding.source}",
            affected_assets=[],
        )
    ]
    report = FindingsReport(
        org_id=0,
        findings=findings,
        summary=_build_summary(findings),
        generated_at="{generated_at}",
        data_sources_used=[],
        assessment_tier="partial",
    )
    prompt, _ = ai_summary._build_prompt(org, report, 50.0, feedback_hint=None)
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ── calls ─────────────────────────────────────────────────────────────────


def _dry_run_call(prompt: str) -> Any:
    """Offline stand-in for the SDK: no network, no key."""
    text = json.dumps(
        {
            "narrative": "Dry run: no model was called.",
            "posture_statement": "Dry run.",
            "notable_risks": [],
            "data_gaps": [],
            "next_steps": [],
        }
    )
    prompt_tokens = math.ceil(len(prompt) / 4)
    out_tokens = math.ceil(len(text) / 4)
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason="STOP")],
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=out_tokens,
            thoughts_token_count=0,
            total_token_count=prompt_tokens + out_tokens,
        ),
        model_version="dry-run-fake",
    )


def _as_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _finish_reason(response: Any) -> str | None:
    try:
        reason = response.candidates[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None
    if reason is None:
        return None
    return str(getattr(reason, "name", reason))


def _usage(response: Any) -> dict[str, int | None]:
    meta = getattr(response, "usage_metadata", None)
    return {f: _as_int(getattr(meta, f, None)) for f in _USAGE_FIELDS}


def _text(response: Any) -> tuple[str | None, str | None]:
    """The response text, or the class of the error raised reading it."""
    try:
        return response.text, None
    # google-generativeai raised here on a blocked/empty response; google-genai
    # returns None instead, which _strict_parse then records as NoText.
    except Exception as exc:  # noqa: BLE001
        return None, type(exc).__name__


def _strict_parse(raw: str | None) -> tuple[bool, str | None]:
    """Schema-valid per §4: parses with no repair (no fence stripping)."""
    if raw is None:
        return False, "NoText"
    try:
        StructuredSummary.model_validate_json(raw)
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        return False, type(exc).__name__
    return True, None


def _estimate_cost(prompt: str, config: EvalConfig, pricing: Pricing) -> float:
    """Worst case for a call with the pinned settings.

    max_output_tokens caps response and thinking tokens together on Gemini
    3.x, so it bounds the billed output. B0 runs production's uncapped call,
    where this can undercount; the tally then switches to the actual cost, so
    the cap is overshot by at most one call's excess.
    """
    return call_cost_usd(
        pricing,
        prompt_tokens=math.ceil(len(prompt) / CHARS_PER_TOKEN_ESTIMATE),
        candidates_tokens=config.max_output_tokens,
        thoughts_tokens=0,
    )


def _derived_thoughts(usage: dict[str, int | None]) -> int | None:
    """Thinking tokens implied by the total when the SDK doesn't report them.

    google-generativeai 0.8.3's UsageMetadata has no thoughts_token_count, but
    Gemini 3.x always thinks and bills it as output. The total is
    prompt + candidates + thoughts (prompt already includes cached tokens).
    """
    if usage["thoughts_token_count"] is not None:
        return None
    parts = (
        usage["total_token_count"],
        usage["prompt_token_count"],
        usage["candidates_token_count"],
    )
    if None in parts:
        return None
    total, prompt, candidates = parts
    return max(0, total - prompt - candidates)


def _actual_cost(usage: dict[str, int | None], pricing: Pricing) -> float | None:
    if usage["prompt_token_count"] is None or usage["candidates_token_count"] is None:
        return None
    thoughts = usage["thoughts_token_count"]
    if thoughts is None:
        thoughts = _derived_thoughts(usage) or 0
    return call_cost_usd(
        pricing,
        prompt_tokens=usage["prompt_token_count"],
        candidates_tokens=usage["candidates_token_count"],
        thoughts_tokens=thoughts,
    )


# ── files ─────────────────────────────────────────────────────────────────


def _append_line(path: Path, record: dict) -> None:
    """Append one JSON line and fsync, so the log and spend tally survive a crash."""
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


# ── main ──────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m evals.ai_summary.run_eval")
    p.add_argument("--run-id", required=True)
    p.add_argument("--split", choices=["dev", "heldout", "all"], required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--max-calls", type=int, required=True)
    p.add_argument("--max-spend-usd", type=float, required=True)
    p.add_argument("--pricing", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dataset", default=DEFAULT_DATASET, help="version name or path")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    p.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    return p.parse_args(argv)


def _check(args: argparse.Namespace) -> tuple[EvalConfig, Pricing, Dataset, str | None]:
    """Every guard that can refuse the run, before anything is written."""
    if not RUN_ID_RE.match(args.run_id) or ".." in args.run_id:
        raise RefusedError("run id must be letters, digits, '.', '_' or '-'")
    if args.split in ("heldout", "all") and not heldout_allowed(args.run_id):
        raise RefusedError("held-out runs are reserved for run ids starting B0, B1 or F")
    if args.repeats < 1 or args.max_calls < 1 or not args.max_spend_usd > 0:
        raise RefusedError("--repeats and --max-calls must be >= 1, --max-spend-usd > 0")

    config = load_config(args.config)
    pricing = load_pricing(args.pricing)
    dataset = load_dataset(resolve_dataset(args.dataset))
    if not dataset.select(args.split):
        raise RefusedError(f"no {args.split} cases in dataset {dataset.version}")

    key = None if args.dry_run else _check_real_run(args, config, pricing, dataset)
    return config, pricing, dataset, key


def _check_real_run(
    args: argparse.Namespace, config: EvalConfig, pricing: Pricing, dataset: Dataset
) -> str:
    """Guards for a run that calls the model; returns the key."""
    if dataset.version == FIXTURE_VERSION and heldout_allowed(args.run_id):
        raise RefusedError("B0, B1 and F runs cannot use the fixture dataset")
    planned = len(dataset.select(args.split)) * args.repeats
    if heldout_allowed(args.run_id) and (
        args.repeats != REPORTED_REPEATS or args.max_calls < planned
    ):
        # A reported run consumes the held-out split once; it must not stop short.
        raise RefusedError(
            f"B0, B1 and F runs need --repeats {REPORTED_REPEATS} and "
            f"--max-calls >= the {planned} planned calls"
        )
    if not pricing.verified:
        raise RefusedError("pricing file is unverified; real runs need a dated, checked file")
    if pricing.model != config.model or ai_summary.settings.GEMINI_MODEL != config.model:
        raise RefusedError("production model, pricing model and eval_config model differ")
    key = _load_key(args.env_file)
    if key is None:
        raise RefusedError("key not set")
    return key


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config, pricing, dataset, key = _check(args)
        base = args.runs_dir / DRY_SUBDIR if args.dry_run else args.runs_dir
        run_dir = base / args.run_id
        if run_dir.exists():
            raise RefusedError(f"run {args.run_id} already exists; run ids are never reused")
    except RefusedError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED

    cases = dataset.select(args.split)
    planned = len(cases) * args.repeats
    git_sha = _git("rev-parse", "HEAD")
    date = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    meta: dict[str, Any] = {
        "run_id": args.run_id,
        "status": "running",
        "dry_run": args.dry_run,
        "split": args.split,
        "repeats": args.repeats,
        "date": date,
        "git_sha": git_sha,
        "git_dirty": bool(_git("status", "--porcelain")),
        "harness_patch_sha": _harness_patch_sha(),
        "ai_summary_py_sha256": file_sha256(Path(_ai_summary_path())),
        "sdk_name": "dry-run-fake" if args.dry_run else _sdk_name_of(ai_summary),
        "sdk_version": None,
        "sdk_versions_installed": {
            "google-generativeai": _installed("google-generativeai"),
            "google-genai": _installed("google-genai"),
        },
        "production_model": ai_summary.settings.GEMINI_MODEL,
        "config_path": args.config.name,
        "config_hash": file_sha256(args.config),
        "config": config.model_dump(),
        "dataset_version": dataset.version,
        "dataset_path": dataset.path.resolve().relative_to(BACKEND_DIR).as_posix()
        if dataset.path.resolve().is_relative_to(BACKEND_DIR)
        else str(dataset.path.resolve()),
        "manifest_hash": dataset.manifest_hash,
        "prompt_template_sha256": prompt_template_sha256(),
        "pricing_file": args.pricing.name,
        "pricing_hash": file_sha256(args.pricing),
        "pricing_verified": pricing.verified,
        "max_calls": args.max_calls,
        "max_spend_usd": args.max_spend_usd,
        "planned_calls": planned,
        "calls_made": 0,
        "spend_usd": 0.0,
    }
    if not args.dry_run:
        meta["sdk_version"] = meta["sdk_versions_installed"].get(meta["sdk_name"])

    run_dir.mkdir(parents=True)
    _write_json(run_dir / "run_meta.json", meta)
    # Logged before the first call, so a crashed held-out run is still disclosed.
    _append_line(base / "index.jsonl", {f: meta[f] for f in INDEX_FIELDS})
    responses = run_dir / "responses.jsonl"
    responses.touch()

    call = _dry_run_call if args.dry_run else ai_summary._call_gemini_raw
    saved_key = ai_summary.settings.GEMINI_API_KEY
    status = "running"
    try:
        if key is not None:
            ai_summary.settings.GEMINI_API_KEY = key
        status = _run_calls(args, config, pricing, cases, meta, call, responses)
    except BaseException:
        # Ctrl-C or a harness crash: never let the run read as completed.
        status = "interrupted"
        raise
    finally:
        ai_summary.settings.GEMINI_API_KEY = saved_key
        meta["status"] = status
        _write_json(run_dir / "run_meta.json", meta)

    print(
        f"{args.run_id}: {status}, {meta['calls_made']}/{planned} calls, "
        f"${meta['spend_usd']:.4f} of ${args.max_spend_usd:.4f}"
    )
    return EXIT_OK if status == "completed" else EXIT_ABORTED


def _run_calls(args, config, pricing, cases, meta, call, responses) -> str:
    """Repeat-major loop, so an abort leaves whole repeats behind it."""
    for repeat in range(1, args.repeats + 1):
        for case in cases:
            aborted = _one_call(args, config, pricing, case, repeat, meta, call, responses)
            if aborted:
                return aborted
    return "completed"


def _one_call(args, config, pricing, case, repeat, meta, call, responses) -> str | None:
    """Make one call and log it. Returns an abort status, or None to continue."""
    if meta["calls_made"] >= args.max_calls:
        print(f"abort: --max-calls {args.max_calls} reached", file=sys.stderr)
        return "aborted_max_calls"

    org, report, risk_score = build_inputs(case)
    prompt, _ = ai_summary._build_prompt(org, report, risk_score, feedback_hint=None)
    estimate = _estimate_cost(prompt, config, pricing)
    if meta["spend_usd"] + estimate > args.max_spend_usd:
        print(
            f"abort: next call (~${estimate:.4f}) would exceed --max-spend-usd "
            f"{args.max_spend_usd}",
            file=sys.stderr,
        )
        return "aborted_spend_cap"

    started = time.perf_counter()
    error_class = None
    response = None
    interrupted: BaseException | None = None
    try:
        response = call(prompt)
    except Exception as exc:  # noqa: BLE001 - class only; messages can carry the key
        error_class = type(exc).__name__
    except BaseException as exc:  # noqa: BLE001 - logged, then re-raised below
        # Ctrl-C mid-call: the request may already be billed, so log and tally it.
        error_class = type(exc).__name__
        interrupted = exc
    latency_ms = int((time.perf_counter() - started) * 1000)

    raw_text, text_error = (None, None) if response is None else _text(response)
    usage = _usage(response)
    cost = _actual_cost(usage, pricing)
    parse_ok, parse_error = _strict_parse(raw_text)
    record = {
        "request_hash": hashlib.sha256(f"{config.model}\n{prompt}".encode()).hexdigest(),
        "case_id": case.id,
        "split": case.split,
        "category": case.category,
        "repeat": repeat,
        "raw_text": raw_text,
        "parse_ok": parse_ok,
        "parse_error_class": parse_error,
        "finish_reason": _finish_reason(response),
        "usage_metadata": usage,
        "thoughts_tokens_derived": _derived_thoughts(usage),
        "latency_ms": latency_ms,
        "model_version": None
        if response is None
        else (str(v) if (v := getattr(response, "model_version", None)) else None),
        "error_class": error_class or text_error,
        "cost_usd": cost,
        "cost_usd_estimate": estimate,
    }
    _append_line(responses, record)
    meta["calls_made"] += 1
    # Use the real cost when the API reports usage; otherwise count the estimate.
    meta["spend_usd"] += cost if cost is not None else estimate
    outcome = "ok" if parse_ok else (record["error_class"] or "unparsed")
    print(f"[{meta['calls_made']}/{meta['planned_calls']}] {case.id} r{repeat} {outcome}")
    if interrupted is not None:
        raise interrupted
    return None


if __name__ == "__main__":
    sys.exit(main())
