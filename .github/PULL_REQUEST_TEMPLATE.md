## Summary

<!-- 1–3 bullets describing what changed and why. -->

## Test plan

<!-- How did you verify this works? -->

## Pre-merge checklist

- [ ] **Tests run locally before requesting review.** Backend: `make backend-test`. Frontend: `cd frontend && npm test`. CI green is necessary but not sufficient — AI-generated tests have shipped against an *imagined* version of the UI/API contract before, passing CI but failing on rerun. See `docs/BROKEN_TEST_REMEDIATION.md`.
- [ ] If this PR adds or modifies tests under `frontend/src/**/__tests__/**` or `*.test.tsx`, the mock fixtures match the real schemas in `frontend/src/api/` (canonical TS) and `backend/app/schemas/` (server-side source of truth). Use the typed factories in `frontend/src/test-utils/testHelpers.tsx` (`createMockOrgMember`, `createMockInvite`) rather than inlining mock objects.
- [ ] No new dependencies added without prior approval.
- [ ] Lint/format: `make backend-lint backend-format` and `cd frontend && npm run lint && npm run format`.
