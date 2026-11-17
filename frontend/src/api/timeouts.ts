/** Default request timeout. Long enough to cover a Render cold start (30 s+). */
export const DEFAULT_TIMEOUT_MS = 60_000;

/** For uploads, CSV imports and other calls that can legitimately run long. */
export const LONG_TIMEOUT_MS = 120_000;

const SAFE_METHODS = new Set(["GET", "HEAD"]);

/**
 * The request ran past its timeout. For a write (POST/PUT/PATCH/DELETE) the
 * server may still have applied it, so the message says to refresh first.
 */
export class RequestTimeoutError extends Error {
  readonly method: string;

  constructor(method = "GET") {
    const m = method.toUpperCase();
    super(
      SAFE_METHODS.has(m)
        ? "The server took too long to respond. It may be starting up — please try again in a moment."
        : "The server took too long to respond. Your change may already have been saved — refresh before trying again.",
    );
    this.name = "RequestTimeoutError";
    this.method = m;
  }
}

/**
 * Map an error from fetch or a body read: our timeout becomes
 * RequestTimeoutError; anything else (including the caller's own abort) is
 * returned unchanged.
 */
export function toTimeoutError(
  err: unknown,
  callerSignal?: AbortSignal | null,
  method?: string,
): unknown {
  const timedOut =
    typeof err === "object" &&
    err !== null &&
    (err as { name?: unknown }).name === "TimeoutError" &&
    !callerSignal?.aborted;
  return timedOut ? new RequestTimeoutError(method) : err;
}

/**
 * AbortSignal.any where available (Chrome 116, Firefox 124, Safari 17.4);
 * otherwise a controller that aborts with whichever input fires first,
 * keeping its reason so TimeoutError / AbortError names survive.
 */
export function anySignal(a: AbortSignal, b: AbortSignal): AbortSignal {
  if (typeof AbortSignal.any === "function") return AbortSignal.any([a, b]);

  const controller = new AbortController();
  for (const s of [a, b]) {
    if (s.aborted) {
      controller.abort(s.reason);
      return controller.signal;
    }
  }
  const onAbortA = () => controller.abort(a.reason);
  const onAbortB = () => controller.abort(b.reason);
  a.addEventListener("abort", onAbortA, { once: true });
  b.addEventListener("abort", onAbortB, { once: true });
  controller.signal.addEventListener(
    "abort",
    () => {
      a.removeEventListener("abort", onAbortA);
      b.removeEventListener("abort", onAbortB);
    },
    { once: true },
  );
  return controller.signal;
}
