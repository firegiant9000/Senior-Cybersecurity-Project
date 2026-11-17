# fetchWithAuth Request Timeouts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `fetchWithAuth` call times out (60 s default, 120 s for uploads, imports and economics) with a readable `RequestTimeoutError`. A caller's own abort still surfaces as `AbortError`.

**Architecture:** `fetchWithAuth` combines `AbortSignal.timeout(timeoutMs)` with the caller's signal through `AbortSignal.any`. A rejection caused by the timeout becomes `RequestTimeoutError`; everything else is rethrown untouched. `getJsonAuth` applies the same conversion to its body read. The constants live in a new `src/api/timeouts.ts`, so the many test files that `vi.mock` `fetchWithAuth` don't need updating when call sites import `LONG_TIMEOUT_MS`.

**Tech Stack:** React + TypeScript, Vitest 4 with jsdom 28, npm (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-11-17-fetchwithauth-timeouts-design.md`

## Global Constraints
- `DEFAULT_TIMEOUT_MS = 60_000` and `LONG_TIMEOUT_MS = 120_000`.
- GET/HEAD message, verbatim: `The server took too long to respond. It may be starting up — please try again in a moment.`
- Any other method, verbatim: `The server took too long to respond. Your change may already have been saved — refresh before trying again.`
- `RequestTimeoutError.name === "RequestTimeoutError"`. It carries a `method: string` field, upper-cased, defaulting to `"GET"`.
- No automatic retries. No backend changes.
- Worktree: `C:/dev/ht-fetch-timeouts`, branch `fix/fetchwithauth-timeouts`. Run `npm ci` in `frontend/` once before the first test run. Run vitest as `npx vitest run --root C:/dev/ht-fetch-timeouts/frontend <path>`.
- One shell command per Bash call (no `&&` or `;`). Never add Claude attribution to commits.

## Review Focus
1. **Test files that `vi.mock("…/fetchWithAuth")` without the new exports.** If a call site imported `LONG_TIMEOUT_MS` from `fetchWithAuth.ts`, those mocks would throw "no export defined". Mitigation: import it from `./timeouts`. Covered by the full-suite run in Task 2.
2. **Existing tests that assert the exact `fetch` init object** (`toHaveBeenCalledWith(url, { method: "POST" })` without `objectContaining`). They break once a `signal` is added. Covered by the full-suite run in both tasks: fix the assertion with `expect.objectContaining`, never by dropping the signal.
3. **A caller abort racing the timeout.** If the caller's signal is aborted, the error must stay `AbortError`, even if the timeout signal has also fired. Test: `"caller abort wins over timeout"` in Task 1.
4. **`timeoutMs` leaking into the `fetch` init.** It is not a `RequestInit` key. Test: `"does not pass timeoutMs through to fetch"` in Task 1.
5. **Pending 60 s timers in every other test.** They must not make the suite hang or slow it noticeably. Check: the full-suite run time stays close to baseline (~915 tests). Report the time.

---

### Task 1: Timeout in `fetchWithAuth` and `getJsonAuth` (model: sonnet)

**Files:**
- Create: `frontend/src/api/timeouts.ts`
- Modify: `frontend/src/api/fetchWithAuth.ts` (all of it, 83 lines)
- Test: `frontend/src/api/fetchWithAuth.test.ts` (extend; add new `describe` blocks)

**Interfaces:**
- Produces, in `timeouts.ts`: `export const DEFAULT_TIMEOUT_MS = 60_000; export const LONG_TIMEOUT_MS = 120_000;`
- Produces, in `fetchWithAuth.ts`:
  - `export class RequestTimeoutError extends Error { readonly method: string; constructor(method?: string) }`. It picks the message from the Global Constraints.
  - `export type FetchWithAuthOptions = RequestInit & { timeoutMs?: number }`
  - `fetchWithAuth(url: string, options?: FetchWithAuthOptions): Promise<Response>`
  - `getJsonAuth<T>(url: string, signal: AbortSignal): Promise<T>`, signature unchanged.
- Re-export `DEFAULT_TIMEOUT_MS` and `LONG_TIMEOUT_MS` from `fetchWithAuth.ts` as well, for convenience. Call sites must import them from `./timeouts` (Review Focus 1).

- [ ] **Step 1: Write the failing tests.** Add this helper and a `describe("timeouts")` inside the existing `describe("fetchWithAuth")`:

```ts
// fetch that never resolves but honours the abort signal, like real fetch
function hangingFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(
    (_url, init) =>
      new Promise<Response>((_resolve, reject) => {
        const s = init?.signal;
        s?.addEventListener("abort", () => reject(s.reason), { once: true });
      }),
  );
}
```

Tests (use `{ timeoutMs: 20 }` in each, so they run on real timers, apart from the default-timeout test):
- `"rejects with RequestTimeoutError on timeout (GET wording)"`: `rejects.toBeInstanceOf(RequestTimeoutError)`, and `rejects.toThrow("It may be starting up")`.
- `"uses the may-already-be-saved wording for a timed-out POST"`: `{ method: "post", timeoutMs: 20 }` gives an error with `.method === "POST"`, and the message contains `"Your change may already have been saved"`.
- `"applies the 60 s default when timeoutMs is omitted"`: spy `vi.spyOn(AbortSignal, "timeout")`, call with a resolving fetch, and expect `toHaveBeenCalledWith(60_000)`. This needs no waiting.
- `"does not pass timeoutMs through to fetch"`: with a resolving fetch, `spy.mock.calls[0][1]` has no `timeoutMs` key and has a `signal` that is an `AbortSignal`.
- `"caller abort still rejects with AbortError, not RequestTimeoutError"`: create an `AbortController`, call with `{ signal: ac.signal, timeoutMs: 1000 }`, then `ac.abort()`. Expect a rejection with `name === "AbortError"` and `not.toBeInstanceOf(RequestTimeoutError)`.
- `"caller abort wins over timeout"`: the caller passes an already-aborted signal and `timeoutMs: 0`. Expect `name === "AbortError"`.
- `"a fast response is unaffected"`: a resolving fetch with `timeoutMs: 20` returns the response, and the promise does not reject after `await new Promise(r => setTimeout(r, 40))`.

In `describe("getJsonAuth")`:
- `"converts a body-read timeout into RequestTimeoutError"`: fetch resolves `{ status: 200, ok: true, json: vi.fn().mockRejectedValue(new DOMException("signal timed out", "TimeoutError")) }`. Expect `getJsonAuth(url, new AbortController().signal)` to reject with `RequestTimeoutError`.
- `"leaves a body-read AbortError from the caller untouched"`: `json` rejects with `new DOMException("aborted", "AbortError")` and the caller's controller is aborted. Expect `name === "AbortError"`.

- [ ] **Step 2: Run them and confirm they fail.**
Run: `npx vitest run --root C:/dev/ht-fetch-timeouts/frontend src/api/fetchWithAuth.test.ts`
Expected: the new tests FAIL (`RequestTimeoutError` is not exported), and the existing 16 still PASS.

- [ ] **Step 3: Implement.**
- Create `timeouts.ts` with the two constants.
- In `fetchWithAuth`:
  - destructure `{ timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...init }`;
  - set `timeoutSignal = AbortSignal.timeout(timeoutMs)`;
  - set `signal = callerSignal ? AbortSignal.any([callerSignal, timeoutSignal]) : timeoutSignal`;
  - wrap only the `fetch(...)` call in try/catch.
- Add a private helper `isTimeout(err: unknown, callerSignal?: AbortSignal | null): boolean`. It returns true when `err` is an object with `name === "TimeoutError"` and `!callerSignal?.aborted`.
  - Both `fetchWithAuth` and `getJsonAuth` use it. In `getJsonAuth`, wrap `response.json()` only.
  - On true, throw `new RequestTimeoutError(init.method)`. Otherwise rethrow.
- Leave the 401/403 handling unchanged.

- [ ] **Step 4: Run them and confirm they pass.**
Same command. Expected: every test in the file PASSES.
If a real-timer test is flaky, raise its wait margin. Don't switch to fake timers unless you've confirmed they drive jsdom's `AbortSignal.timeout`. Note your choice in a one-line comment above `hangingFetch`.

- [ ] **Step 5: Run the full frontend suite** to catch Review Focus 2 and 5.
Run: `npx vitest run --root C:/dev/ht-fetch-timeouts/frontend > <scratchpad>/vitest-t1.log 2>&1`. Read only the summary and the failures.
Expected: all files pass, with test count = baseline 915 + the new tests. Fix any exact-`fetch`-init assertion with `expect.objectContaining`.

- [ ] **Step 6: Commit**
```
git -C C:/dev/ht-fetch-timeouts add frontend/src/api/timeouts.ts frontend/src/api/fetchWithAuth.ts frontend/src/api/fetchWithAuth.test.ts
git -C C:/dev/ht-fetch-timeouts commit -m "feat(api): request timeouts in fetchWithAuth with RequestTimeoutError"
```
(Add any test files fixed in Step 5 to the same commit.)

Hard stop at 80 tool calls: commit what is done, report what remains.

---

### Task 2: Long timeouts at the slow call sites, then the gate (model: haiku)

**Files:**
- Modify: `frontend/src/api/uploads.ts:48` (`uploadFile`)
- Modify: `frontend/src/api/inventory.ts:55`, `:69` (`previewInventoryCsv`, `importInventoryCsv`)
- Modify: `frontend/src/api/vendors.ts:101`, `:125` (`importVendorsCsv`, `previewVendorsCsv`)
- Modify: `frontend/src/components/tabs/EconomicsTable.tsx:76`
- Create test: `frontend/src/api/__tests__/longTimeouts.test.ts`

**Interfaces:**
- Consumes: `LONG_TIMEOUT_MS` from `frontend/src/api/timeouts.ts`, and `fetchWithAuth(url, options?: FetchWithAuthOptions)` from Task 1.

- [ ] **Step 1: Write the failing test** `longTimeouts.test.ts`:
  - `vi.mock("../fetchWithAuth", ...)` with `API_BASE_URL: "http://api.test"` and `fetchWithAuth: vi.fn()`. The mock resolves `{ ok: true, status: 200, json: async () => ({}) }`.
  - Add one `it` per function: `uploadFile(1, file)`, `previewInventoryCsv(1, file)`, `importInventoryCsv(1, file)`, `importVendorsCsv(1, file)`, `previewVendorsCsv(1, file)`. Use `const file = new File(["a"], "a.csv")`.
  - Each asserts `expect(fetchWithAuth).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ timeoutMs: LONG_TIMEOUT_MS }))`.
  - Import `LONG_TIMEOUT_MS` from `"../timeouts"`.
  - EconomicsTable is covered by Step 4's typecheck plus a read of the diff. Don't add a component test for it.

- [ ] **Step 2: Run it and confirm it fails.**
Run: `npx vitest run --root C:/dev/ht-fetch-timeouts/frontend src/api/__tests__/longTimeouts.test.ts`. Expected: 5 FAIL.

- [ ] **Step 3: Add `timeoutMs: LONG_TIMEOUT_MS` to each call's options.**
- Import it from `./timeouts`, or from `../../api/timeouts` in EconomicsTable.
- EconomicsTable currently passes `signal ? { signal } : undefined`. Change that to `{ signal, timeoutMs: LONG_TIMEOUT_MS }`.

- [ ] **Step 4: Run the gate** (from `frontend/`):
  - `npm run lint`: expected 0 problems.
  - `npm run build`: expected success. It runs `tsc` and the vite build.
  - `npx vitest run --root C:/dev/ht-fetch-timeouts/frontend > <scratchpad>/vitest-t2.log 2>&1`: expected all pass. Report the file and test counts against the baseline of 70 files / 915 tests, and the act-warning count against the baseline of 7.
  - Clean up any `vite.config.js`, `vite.config.d.ts` or `*.tsbuildinfo` files the build emits, if `git status` shows them.

- [ ] **Step 5: Commit**
```
git -C C:/dev/ht-fetch-timeouts add frontend/src/api/uploads.ts frontend/src/api/inventory.ts frontend/src/api/vendors.ts frontend/src/components/tabs/EconomicsTable.tsx frontend/src/api/__tests__/longTimeouts.test.ts
git -C C:/dev/ht-fetch-timeouts commit -m "feat(api): 120 s timeout for uploads, CSV imports and economics"
```

Hard stop at 80 tool calls: commit what is done, report what remains.
