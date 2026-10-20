# AI summary eval harness

Offline tooling for the S5a evaluation. The rules (dataset, runs, metrics and
claims) are in [`docs/ai/eval-protocol.md`](../../../docs/ai/eval-protocol.md);
this folder implements them. It is not part of the app and never runs in CI
against the real model. CI runs only its unit tests (`tests/evals/`).

| File | Purpose |
|---|---|
| `eval_config.yaml` | Pinned model settings (§1). Every key is required. B0 runs the shipped code, which does **not** apply them; production adopts them in stage C (B1) |
| `pricing-TEMPLATE.yaml` | Unverified price table. Dry runs only; a real run needs a dated `pricing-YYYY-MM-DD.yaml` with `verified: true`, `checked_on` and `source_url` |
| `dataset/<version>/` | `cases.jsonl` + `MANIFEST.json` (+ `CHANGELOG.md`). `v1/` (27 dev / 22 held-out, synthetic) is the default and is frozen; `fixture/` is a three-case smoke set for tests, never reported |
| `dataset/generate_v1.py` | Seeded generator for `v1/`. `python evals/ai_summary/dataset/generate_v1.py --check` verifies the committed files byte for byte |
| `attack_strings.py` | The six attack types' templates: `V1_TEMPLATES` (frozen with `v1/`) plus `CORPUS_ONLY_TEMPLATES`, rendered by `corpus()` for the stage-D CI corpus (CI-only canaries, no case data) |
| `rubric_v1.md` | How to judge attack repeats in `manual_judgement.csv`, with the one-line-rationale rule |
| `run_eval.py` | Renders the production prompt and calls the production SDK seam, `_call_gemini_raw`, bypassing the DB last-good fallback |
| `score.py` | Pure re-scoring of stored responses; writes `scores.json` and `manual_judgement.csv` |
| `stats.py` | Wilson interval, exact McNemar, B1→F flips |
| `runs/` | One folder per real run plus `index.jsonl`. `runs/_dry/` is gitignored |

Run from `backend/`:

```sh
# Offline: fake client, no key, no network. Output goes to runs/_dry/.
python -m evals.ai_summary.run_eval --run-id DRY1 --split dev --repeats 1 \
  --max-calls 5 --max-spend-usd 0.01 \
  --pricing evals/ai_summary/pricing-TEMPLATE.yaml --dry-run
python -m evals.ai_summary.score --run-id DRY1 --dry-run
```

**Guards** (each refuses before anything is written; exit code 2):
- `--split heldout|all` only for run ids starting `B0`, `B1` or `F`, dry runs included (use for example `B0-DRY`);
- a real run needs verified pricing, a key in `backend/.env.local`, and the same model in production, pricing and config;
- real B0, B1 and F runs refuse the fixture dataset, and need `--repeats 3`
  and a `--max-calls` that covers every planned call; run ids are never reused;
- a dataset that no longer matches its manifest is refused by both scripts.

**Spend** (exit code 3 on abort): before each call the runner estimates its
cost (prompt characters / 3 as input tokens, plus `max_output_tokens` as
output, which on Gemini 3.x caps thinking and response together) and stops if
the running total plus that estimate would pass `--max-spend-usd`. It also
stops after `--max-calls`. The total uses each call's real `usage_metadata`
cost when the API reports it.
- B0 runs without the config's output cap or thinking level, so one call can
  cost more than its estimate. The cap then holds to within one call.
- A call that returns no usage (an API error) is tallied at its estimate, so
  `spend_usd` overstates a run with errors. Failed calls aren't billed.
- `google-generativeai` 0.8.3 reports neither `thoughts_token_count` nor
  `model_version`. Gemini 3.x always thinks and bills that as output, so the
  runner derives thinking tokens as `total - prompt - candidates`, logs them
  as `thoughts_tokens_derived`, and costs them. `model_version` stays null on
  every B0 row; the report must say so.
- A Ctrl-C or crash marks the run `interrupted`. The in-flight call is logged
  by error class and tallied at its estimate, because it may already be
  billed.
- The runner makes no retries of its own. Stage C must confirm that the SDK
  doesn't retry silently either.
- The cap applies per run. Every call is fsynced to `responses.jsonl` with its
  cost, so a crash loses no tally. A crashed run can't be resumed under the
  same id, though, and nothing caps the total across runs.

**Scoring notes:**
- An API error, timeout or blocked response on an attack case is
  *indeterminate*, not an injection success. It is counted per case as
  `indeterminate_repeats`. A case with no answered repeat leaves `n` and is
  listed in `indeterminate_cases`. The per-repeat `repeat_rates` count
  answered repeats only (`null` where none answered), so an indeterminate
  repeat is never counted as a defence.
- `fallback_stage_d_policy` is the rate the template would apply after stage
  D. B0/B1 production instead serves fence-stripped raw text when parsing
  fails, so don't report it as their fallback rate.
- KEV ground truth ranks only the 20 findings the prompt shows, in the
  engine's order.

**Key:** read only from `backend/.env.local` (`GEMINI_API_KEY`), never from
the process environment, and never printed, logged or written. API errors are
recorded by exception class only, because their messages can carry the request
URL. A missing key prints `key not set` and nothing else.
