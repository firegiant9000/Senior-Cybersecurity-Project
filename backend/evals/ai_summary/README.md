# AI summary eval harness

Offline tooling for the S5a evaluation. The rules (dataset, runs, metrics and
claims) are in [`docs/ai/eval-protocol.md`](../../../docs/ai/eval-protocol.md);
this folder implements them. It is not part of the app and never runs in CI
against the real model. CI runs only its unit tests (`tests/evals/`).

| File | Purpose |
|---|---|
| `eval_config.yaml` | Pinned model settings (§1). Every key is required. B0 runs the shipped code, which does **not** apply them; production adopts them in stage C (B1) |
| `pricing-TEMPLATE.yaml` | Unverified price table. Dry runs only; a real run needs a dated `pricing-YYYY-MM-DD.yaml` with `verified: true`, `checked_on` and `source_url` |
| `dataset/<version>/` | `cases.jsonl` + `MANIFEST.json`. `fixture/` is a three-case smoke set that is never reported; `v1/` arrives in stage B |
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
- real B0, B1 and F runs refuse the fixture dataset; run ids are never reused;
- a dataset that no longer matches its manifest is refused by both scripts.

**Spend** (exit code 3 on abort): before each call the runner estimates its
cost (prompt characters / 3 as input tokens, plus `max_output_tokens` and
`thinking_budget` as output) and stops if the running total plus that estimate
would pass `--max-spend-usd`. It also stops after `--max-calls`. The total uses
each call's real `usage_metadata` cost when the API reports it.
- B0 runs without the config's output cap or thinking budget, so one call can
  cost more than its estimate. The cap then holds to within one call.
- The runner makes no retries of its own. Stage C must confirm that the SDK
  doesn't retry silently either.
- The cap applies per run. Every call is fsynced to `responses.jsonl` with its
  cost, so a crash loses no tally. A crashed run can't be resumed under the
  same id, though, and nothing caps the total across runs.

**Key:** read only from `backend/.env.local` (`GEMINI_API_KEY`), never from
the process environment, and never printed, logged or written. API errors are
recorded by exception class only, because their messages can carry the request
URL. A missing key prints `key not set` and nothing else.
