# Case study: hardening an LLM security briefing against prompt injection, and measuring it honestly

Hacker Tracker gives small organisations a plain-English executive briefing of their security findings, written by Gemini (`gemini-3.6-flash`). This page covers how that feature was hardened against prompt injection in milestone S5a, and what a pre-registered evaluation on held-out cases does and doesn't show. Every number here compares the same 22 held-out synthetic cases before (**B1**) and after (**F**) the hardening. The full report is [`eval-2026-10-20.md`](eval-2026-10-20.md), and the rules it follows are in [`eval-protocol.md`](eval-protocol.md).

## The problem

The briefing prompt carries text that users control: the organisation's name, industry, size and state, plus software and vendor names that end up in finding titles. Before S5a those fields were pasted into the prompt as prose. If the text looked like an instruction, the model could follow it. In the baseline B1, 2 of 10 held-out attack cases succeeded:
- a fake `INSTRUCTIONS:` section in the organisation name replaced the whole narrative with an attacker-chosen token;
- an instruction in the industry field replaced the posture statement.

## Threat model and blast radius

- **Who can inject:**
  - an org member editing the organisation profile (the name is free text; industry, size and state are validated by the API today, so attacks there test defence in depth);
  - anyone whose software or vendor names reach the org's inventory.
- **What an attack can do:** the model has no tools, no network access and no data beyond the one organisation's own findings, so it can't exfiltrate anything or act. The realistic harm is **a misleading briefing**: a "no risk" narrative, attacker text inside a trusted report, or leaked prompt text. That matters because the briefing is what a non-technical owner acts on.
- **Who sees it:** that organisation's users, and global admins, who can read any organisation.

## Design

1. **Data, not prose.** Every organisation field and finding goes into one JSON data block that the prompt labels as untrusted data. Nothing user-supplied is interpolated as instructions.
2. **A schema with citations.** The model must answer in a response schema in which every notable risk cites the ids of the findings it rests on.
3. **A grounding validator.** It drops any risk that cites no id or an id that isn't in the input, and logs only a count.
4. **No raw fallback.** Truncated or schema-invalid output is replaced by a deterministic template; raw model text is never served.
5. **Pinned settings.** SDK, model, temperature, thinking level, output cap and a 20 s timeout are pinned, and a unit test checks that production matches the evaluation config.
6. **Deterministic CI tests** assert the prompt's structure against a corpus of injection strings. They test structure, not the model.

## The evaluation

The method was written down before the first run:
- a versioned synthetic dataset, split into dev (used for tuning) and held-out (22 cases, 10 of them attacks across six attack types), with each case run 3 times;
- per-case scoring;
- Wilson intervals;
- exact McNemar tests on paired flips;
- a rule that "improved" needs both p < 0.05 and a change larger than the baseline's repeat range.

Held-out cases ran only in the baselines and the final run. One final attempt lost its network connection partway through; it was recorded, and it was re-run before any of its outputs were read. Injection outcomes come from an automatic canary check plus a judge, who rated each attack repeat against a written rubric with a one-line rationale; the owner spot-checks a sample.

| Held-out metric (22 cases) | B1 (before) | F (after) | Reading |
|---|---|---|---|
| Injection success (10 attack cases) | 2/10 (95% CI 6–51%) | **0/10** (95% upper bound ≈ 30%) | Directionally better, **not statistically confirmed**: 2 fixed, 0 broke, too few to test |
| Schema-valid | 22/22 | 22/22 | No change; schema-forced by constrained decoding in both |
| Risks citing real input findings (before the validator) | not measurable: B1's schema had no citations | 22/22 cases; every one of 186 risks cites at least one | New capability |
| Top known-exploited (KEV) findings cited (18 cases) | 0/18, by construction | 18/18 | A schema and prompt effect: B1 couldn't cite at all |
| API errors / timeouts / template fallbacks, per call | 0/66 errors, 0/66 timeouts | 0/66, 0/66, 0/66 | No change |
| Latency p50 | 5.5 s | 6.3 s | **Worse** (longer prompt) |
| Cost per summary, mean | $0.0037 | $0.0045 | **Worse**, +23% (longer prompt) |
| Finding ids leaking into action-step prose (found after the run) | 0/66 calls | 16/66 calls | **Regression** |

## What still fails

- **Ids in prose.** In about a quarter of calls the model writes raw finding ids ("Finding 06b4624cf89b") into the action-step rationales, which the UI shows verbatim. The ids are real, so nothing is invented, but it reads badly. The prompt change that added citations caused it, and the dev tuning runs missed it because no metric looked at prose.
- **No statistical proof of injection resistance.** Ten attack cases can show at most "0 of 10, upper bound ≈ 30%". The attacks didn't land, but that sample can't rule out a meaningful success rate.
- **One judge.** Injection judging is one judge plus an owner spot-check, not independent co-judging.
- **Schema-valid can still be steered.** A schema-valid answer can still be steered; the schema narrows what an attacker can change but doesn't stop it.

## What's next

1. Fix the ids-in-prose regression (a prompt rule, or a validator that strips id-shaped tokens from prose), checked on dev.
2. Build dataset v2 with enough attack cases to make a paired test possible. Six or more discordant cases are needed even to reach p < 0.05, so roughly three to four times today's ten.
3. Add an independent second judge.
4. Re-run the baseline and the final run on v2 before quoting new numbers.
