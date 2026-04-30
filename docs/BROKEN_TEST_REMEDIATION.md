# Broken Frontend Test Suites — Remediation Plan

## Context

`origin/main` (HEAD `49b4cbb`) currently has **103 failing tests across 6 files**, all AI-generated suites that were merged from `frontend-and-refresh` work. They were never validated locally before merge. CI's `frontend-test` job (`npm test`) is red, which also blocks the `preview-deploy` job downstream (per `.github/workflows/ci.yml`, `preview-deploy` depends on `[frontend-lint, frontend-test]`).

**Current local state (this branch will be `main`):**

| File | Failing | Passing | Total |
|---|---|---|---|
| `frontend/src/App.expanded.test.tsx` | 11 | 51 | 62 |
| `frontend/src/Dashboard.expanded.test.tsx` | 40 | 41 | 81 |
| `frontend/src/__tests__/integration.flows.test.tsx` | 9 | 31 | 40 |
| `frontend/src/pages/__tests__/AcceptInvitePage.expanded.test.tsx` | 19 | 18 | 37 |
| `frontend/src/pages/__tests__/AssessmentDebugPage.expanded.test.tsx` | 19 | 39 | 58 |
| `frontend/src/pages/__tests__/SettingsPage.members.test.tsx` | 5 (was 13) | 63 | 68 |
| `frontend/src/pages/__tests__/AssessmentIntakePage.test.tsx` | 5 | 11 | 16 |
| **Total** | **~103** | **~254** | **~362** |

> Note: `SettingsPage.members.test.tsx` was fixed on branch `frontend-and-refresh` (commit `908b980`); main still carries the broken version until that PR merges. The other 5 suites are broken on both.

The shared root cause: the test files were generated against an *imagined* version of the UI/API contracts rather than the actual code. Recurring failure shapes:

1. **Wrong data shapes in mocks** — e.g. invite mocks used `invited_email` + `error_message` (the public `InviteTokenInfo` shape) when the listing endpoint returns `email` + `status` (the `OrgInvite` shape from `backend/app/schemas/org_invite.py`).
2. **Imagined DOM** — selectors target elements that don't render (e.g. a role `<select>` for the owner row, which renders as a `<span class="role-badge">`).
3. **Ambiguous queries** — `getByText('Email')` when "Email" appears in account info, members header, and invites header simultaneously.
4. **Wrong index assumptions** — `selects[0]` when multiple sections render selects in DOM order the test author misjudged.
5. **Async timing** — calling `screen.getByPlaceholderText` synchronously before the page has loaded the profile.
6. **Asserting on internal error message instead of UI string** — the page wraps `Error("Cannot revoke invite")` into the literal `"Failed to revoke invite"` before rendering.

These tests were not written with a running app in front of them. Patterns 1–6 occur in every one of the 6 files.

## Goal

Get `frontend-test` green on `main` quickly, without permanently dropping the AI-generated tests that *do* exercise real flows. Preserve the ~254 passing tests; isolate the ~103 broken ones for a structured repair.

## Strategy: skip-then-repair, file by file

Rejected alternatives:

- **Fix everything in one PR.** Estimated ~1 day of careful work across 5 files. Blocks deploys for that whole window. Risk of churn-induced regressions in already-passing tests within those files.
- **Revert all the AI suites.** Throws away the 254 passing tests too — many of which exercise legitimate flows (route guarding, role-based tab visibility, intake validation). Net loss of coverage.
- **Rewrite from scratch.** Same downside as revert plus more work.

**Chosen: two-phase plan.**

### Phase 0 — Merge `frontend-and-refresh`

`SettingsPage.members.test.tsx` is already repaired on that branch (commit `908b980`). Land that PR first; it removes one of the six broken files from the list and proves the repair pattern works. No additional work required for this file.

### Phase 1 — Stop the bleed (1 PR, ~30 min)

Mark each remaining broken test with `it.skip(...)` (or `describe.skip` for whole groups) and append `// FIXME(test-repair-#NN)` referencing tracking issues. Why per-test rather than per-file:

- Preserves the 18–51 passing tests in each file.
- The `FIXME` markers make the repair backlog visible in the source instead of hidden in a tracker no one re-opens.
- A skipped test still type-checks, so the file participates in lint/TS coverage.

Concrete steps:
1. Run `npx vitest run --reporter=verbose` and capture the failing test titles per file.
2. For each failing test, change `it(` → `it.skip(` (or `test(` → `test.skip(`).
3. Add a one-line comment: `// FIXME(test-repair): <one-line reason>` — e.g. `// FIXME(test-repair): selects[0] is admin row, but test expects owner; needs DOM audit`.
4. Confirm `npx vitest run` is green locally.
5. PR to main with a short body listing the 5 files and the count skipped. Title: `test(frontend): skip broken AI-generated tests pending repair`.

CI goes green immediately after merge.

### Phase 2 — Repair, one file per PR

Each repair PR follows this checklist (codified from what worked on `SettingsPage.members.test.tsx`):

1. **Read the component first.** Before touching the test, open the file under test and trace what it actually renders for the test's mocked state. Don't trust the test's assumptions.
2. **Align mock fixtures with real schemas.** Cross-reference:
   - Invite-list shape → `backend/app/schemas/org_invite.py::InviteRead` (`email`, `status`, `inviter_id`, `expires_at`, `created_at`)
   - Member-list shape → `org_invite.py::MemberRead`
   - Frontend types → `frontend/src/api/members.ts` (`OrgInvite`, `OrgMember`)
   - Profile shape → whatever `/api/v1/auth/me` returns; check `frontend/src/contexts/AuthContext.tsx`
3. **Disambiguate queries.** `getByText` → `getAllByText[…].length`, `getByRole('button', { name: '×' })` → `getAllByTitle('Revoke invite')`, etc. Prefer queries that scope by section (`within(membersSection).getByText(...)`).
4. **Verify select indices empirically.** Add a temporary `screen.debug()` to confirm DOM order before asserting `selects[N]`.
5. **Mind same-value `fireEvent.change`.** React's `onChange` won't refire if the new value equals the current one. Pick a value that's actually different, or assert via the mock call args, not via downstream UI state.
6. **Trust the page's actual error string.** Page handlers often replace exception messages with a generic UI string before rendering. Assert what the user sees, not what `mockRejectedValue` was constructed with.
7. **Run the targeted file in watch mode** while editing: `npx vitest src/path/to/file.test.tsx`.

Suggested PR sequence (smallest blast radius first):

| Order | File | Why this order |
|---|---|---|
| 1 | `AssessmentIntakePage.test.tsx` (5) | Smallest count; isolated to one page. |
| 2 | `integration.flows.test.tsx` (9) | Cross-cutting but small; surfaces auth/route mocking patterns reused elsewhere. |
| 3 | `App.expanded.test.tsx` (11) | Same routing patterns as #2; can copy the working harness. |
| 4 | `AcceptInvitePage.expanded.test.tsx` (19) | Page-scoped; reuse invite-shape fix from `SettingsPage`. |
| 5 | `AssessmentDebugPage.expanded.test.tsx` (19) | Page-scoped, debug-only path. |
| 6 | `Dashboard.expanded.test.tsx` (40) | Largest; many tab-visibility tests sharing one mock harness. Save for last so earlier PRs derisk the patterns. |

Each PR un-skips its file's tests, fixes them, and removes the FIXME markers. Aim for ~30–60 min per PR; the smaller ones may take 15.

### Phase 3 — Prevention

After Phase 2, lock the door so AI-generated tests can't get re-merged unverified:

- **CODEOWNERS / PR template note** under `frontend/src/**/__tests__/` requiring "tests run locally before merge" — checkbox.
- **Pre-commit hook (optional):** add `cd frontend && npm test --silent --run --bail=1` to a husky `pre-push`. Slower but stops the next round.
- **Type-narrow the mocks.** `testHelpers.tsx` already exports `MockOrgMember` / `MockInvite`. Update them to match the real `OrgInvite` / `OrgMember` interfaces from `frontend/src/api/members.ts`, and have all suites consume the factory functions instead of inlining mock objects. Keeps schema drift from happening again.

## Critical files

- `frontend/src/api/members.ts` — canonical TS shapes for invites/members; mocks must match.
- `backend/app/schemas/org_invite.py` — server-side source of truth.
- `frontend/src/test-utils/testHelpers.tsx` — factories the suites should use; needs schema alignment.
- The 6 broken test files (paths in the table above).

## Verification

Phase 1 done when:
- `cd frontend && npx vitest run` exits 0.
- CI's `frontend-test` job is green on main.
- Each previously-failing test is marked `.skip` with a `// FIXME(test-repair)` comment.

Phase 2 PRs done when:
- The PR's target file has zero `.skip` and zero `FIXME(test-repair)` markers.
- `npx vitest run <file>` is green.
- A reviewer confirms the test mocks reference the real schema (spot-check one or two).

Phase 3 done when:
- `testHelpers.tsx` factories are typed to `OrgInvite` / `OrgMember` from `api/members.ts` (compiler enforces alignment).
- A documented pre-merge step exists in `CONTRIBUTING.md` or the PR template.

## Risks

- **Skipped tests rot.** If Phase 2 stalls, the FIXMEs become permanent. Mitigation: file a tracking issue per file at Phase 1 merge; assign owners.
- **Mock drift between PRs.** If two repair PRs touch `testHelpers.tsx` simultaneously, conflicts. Mitigation: do the type-tightening in Phase 3 *after* all repairs land, not during.
- **Hidden coupling between suites.** A few tests share global mocks (`vi.mock`) at module scope. Skipping individual `it`s leaves the module mocks in place, which is fine — but un-skipping in Phase 2 may surface order-dependent state. If so, isolate with `beforeEach` resets.
