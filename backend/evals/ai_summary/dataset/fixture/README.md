# Fixture dataset (harness smoke test only)

Three hand-written synthetic cases, so the stage A dry run and the harness
tests have something to load before `dataset/v1` exists. **Never report a
number from it.** `run_eval` refuses it for `B0`, `B1` and `F` run ids.

Regenerate the manifest after any edit (from `backend/`):

```sh
python -c "from evals.ai_summary.dataset import FIXTURE_DATASET, write_manifest; write_manifest(FIXTURE_DATASET, version='fixture', date='2026-10-19')"
```
