/**
 * Authenticated fetch wrapper.
 * Automatically attaches the Firebase ID token as a Bearer header.
 */

import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { DEFAULT_TIMEOUT_MS } from "./timeouts";

export { DEFAULT_TIMEOUT_MS, LONG_TIMEOUT_MS } from "./timeouts";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export class ForbiddenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ForbiddenError";
  }
}

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

export type FetchWithAuthOptions = RequestInit & { timeoutMs?: number };

/** True when err came from our timeout, not from the caller's own abort. */
function isTimeout(err: unknown, callerSignal?: AbortSignal | null): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    (err as { name?: unknown }).name === "TimeoutError" &&
    !callerSignal?.aborted
  );
}

// Prevents multiple concurrent 401s from firing multiple sign-outs
let isLoggingOut = false;

/** Reset module state — only for use in tests. */
export function _resetForTest() {
  isLoggingOut = false;
}

export async function fetchWithAuth(
  url: string,
  options: FetchWithAuthOptions = {},
): Promise<Response> {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal: callerSignal,
    ...init
  } = options;
  const user = auth.currentUser;
  const token = user ? await user.getIdToken() : null;

  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const signal = callerSignal
    ? AbortSignal.any([callerSignal, timeoutSignal])
    : timeoutSignal;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      signal,
      headers: {
        ...init.headers,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (err) {
    if (isTimeout(err, callerSignal)) throw new RequestTimeoutError(init.method);
    throw err;
  }

  if (response.status === 401) {
    if (!isLoggingOut) {
      isLoggingOut = true;
      try {
        await signOut(auth);
      } catch {
        // Sign-out failed (e.g. network error); reset so future 401s can retry
      } finally {
        isLoggingOut = false;
      }
    }
    window.location.href = "/login";
    return response;
  }

  if (response.status === 403) {
    const body = await response.json().catch(() => ({}));
    throw new ForbiddenError(
      (body as { detail?: string }).detail ??
        "You do not have permission to perform this action",
    );
  }

  return response;
}

/**
 * Convenience: fetch JSON with auth + error handling.
 */
export async function getJsonAuth<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetchWithAuth(url, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Request failed: ${response.statusText}`,
    );
  }
  try {
    return (await response.json()) as T;
  } catch (err) {
    if (isTimeout(err, signal)) throw new RequestTimeoutError("GET");
    throw err;
  }
}
