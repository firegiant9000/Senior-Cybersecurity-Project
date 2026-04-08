/**
 * Authenticated fetch wrapper.
 * Automatically attaches the Firebase ID token as a Bearer header.
 */

import { signOut } from "firebase/auth";
import { auth } from "../firebase";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export class ForbiddenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ForbiddenError";
  }
}

// Prevents multiple concurrent 401s from firing multiple sign-outs
let isLoggingOut = false;

/** Reset module state — only for use in tests. */
export function _resetForTest() {
  isLoggingOut = false;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const user = auth.currentUser;
  const token = user ? await user.getIdToken() : null;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

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
  return response.json() as Promise<T>;
}
