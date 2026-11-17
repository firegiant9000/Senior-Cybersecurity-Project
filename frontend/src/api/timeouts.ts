/** Default request timeout. Long enough to cover a Render cold start (30 s+). */
export const DEFAULT_TIMEOUT_MS = 60_000;

/** For uploads, CSV imports and other calls that can legitimately run long. */
export const LONG_TIMEOUT_MS = 120_000;
