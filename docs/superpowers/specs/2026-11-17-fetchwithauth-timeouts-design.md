# fetchWithAuth request timeouts — design

**Date:** 2026-11-17 · **Size:** small change · **Status:** awaiting approval

## Intent
`fetchWithAuth` has no timeout. A request that hangs, a POST or DELETE included, leaves the page stuck in its loading state until the user reloads. Every API call should end in an error the page can show.

## Goals
- Every `fetchWithAuth` call times out after **60 s** by default. That limit covers the Render backend's cold start, which can take 30 s or more.
- A per-call `timeoutMs` override. **120 s** for uploads, CSV imports and the economics GET.
- Timeouts surface as a distinct `RequestTimeoutError` with readable text. They must not be mistaken for a caller's own cancel (`AbortError`).

## Non-goals
- No automatic retries, for any method.
- No call-site UI changes beyond the overrides. Existing callers already render `err.message`.
- No backend changes.

## Anti-goals
- Breaking the ~25 callers that ignore `AbortError` on unmount. A caller's own abort must still reach them as `AbortError`.
- Telling the user a timed-out write failed when it may have succeeded.

## Approaches considered
1. **Built-in signals: `AbortSignal.any([callerSignal, AbortSignal.timeout(ms)])`.** Chosen. Little code, and it also covers the body read. jsdom 28 supports both APIs.
2. **Own `AbortController` + `setTimeout`, cleared when the headers arrive.** Rejected. A stalled body can still hang the page, and the timer and listener cleanup is extra code.
3. **Per-call-site timeouts.** Rejected. That means ~100 sites in 34 files.

## Design
- `fetchWithAuth(url, options: RequestInit & { timeoutMs?: number } = {})`
  - `DEFAULT_TIMEOUT_MS = 60_000` and `LONG_TIMEOUT_MS = 120_000`, both exported.
  - `timeoutMs` is stripped from the options before they reach `fetch`.
  - Signal: `AbortSignal.timeout(timeoutMs)`, combined with `options.signal` through `AbortSignal.any` when the caller passes one.
  - On rejection: if the timeout signal fired and the caller's signal did not, throw `RequestTimeoutError`. Otherwise rethrow unchanged, so `AbortError` and `TypeError` keep working.
- `RequestTimeoutError extends Error`, `name = "RequestTimeoutError"`, with a `method` field.
  - GET/HEAD message: "The server took too long to respond. It may be starting up — please try again in a moment."
  - Any other method: "The server took too long to respond. Your change may already have been saved — refresh before trying again."
- `getJsonAuth`: the `response.json()` body read runs under the same signal. If that read rejects because of the timeout, convert it to `RequestTimeoutError`.
  - The timeout check is extracted into a small helper that both functions share.
  - Other helpers that call `response.json()` themselves keep the raw `DOMException` (`TimeoutError`) for a stalled body. That is rare and accepted.
- Call sites given `LONG_TIMEOUT_MS`:
  - `uploads.ts` upload;
  - `inventory.ts` CSV preview and import;
  - `vendors.ts` import and import preview;
  - the economics GET in `EconomicsTable` (on a cold cache the backend makes ~50 sequential BEA calls).

## Retry semantics (non-idempotent requests)
Nothing retries automatically. When a POST/PUT/PATCH/DELETE times out, the message says the change may have been saved and asks the user to refresh first. The server may well finish the work after the client gives up. A user who retries without refreshing can get a duplicate or a 404/409, the same as with any manual double-submit today.

## Testing (TDD, `fetchWithAuth.test.ts`)
The mocked `fetch` honours `init.signal`: it rejects with `signal.reason` when the signal aborts, and stays pending otherwise.
- The default timeout rejects with `RequestTimeoutError` (GET wording).
- POST wording on timeout.
- A `timeoutMs` override is respected, and `timeoutMs` is not passed through to `fetch`.
- A caller abort still rejects with `AbortError`, not `RequestTimeoutError`.
- A fast response is unaffected, and the existing tests still pass.
- `getJsonAuth` converts a body-read timeout.

Timers: try `vi.useFakeTimers()` first. If fake timers don't drive jsdom's `AbortSignal.timeout`, use small real `timeoutMs` values (~20–50 ms) and note why in the test file.

## Left to the builder
- The exact name of the shared timeout-check helper.
- Whether a missing `options.signal` skips `AbortSignal.any`.
