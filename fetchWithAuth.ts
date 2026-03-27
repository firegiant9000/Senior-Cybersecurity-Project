/**
 * Authenticated fetch wrapper.
 * Automatically attaches the Firebase ID token as a Bearer header.
 */

import { auth } from "../firebase";
import { onAuthStateChanged } from "firebase/auth";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

const LOGIN_PATH = "/login";

let authReadyPromise: Promise<void> | null = null;
async function waitForAuthReady(): Promise<void> {
  if (authReadyPromise) return authReadyPromise;
  authReadyPromise = new Promise<void>((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, () => {
      unsubscribe();
      resolve();
    });
  });
  return authReadyPromise;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  // Ensure Firebase auth has finished initializing before checking currentUser.
  await waitForAuthReady();

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
    if (window.location.pathname !== LOGIN_PATH) {
      window.location.assign(LOGIN_PATH);
    }
    throw new Error("Unauthorized");
  }

  if (response.status === 403) {
    throw new Error("Permission Denied");
  }

  return response;
}

/**
 * Convenience: fetch JSON with auth + error handling.
 */
export async function getJsonAuth<T>(url: string, signal?: AbortSignal): Promise<T> {
  try {
    const response = await fetchWithAuth(url, signal ? { signal } : undefined);

    // Fallback (in case a different fetch implementation bypasses fetchWithAuth logic).
    if (response.status === 401) {
      if (window.location.pathname !== LOGIN_PATH) {
        window.location.assign(LOGIN_PATH);
      }
      throw new Error("Unauthorized");
    }
    if (response.status === 403) {
      throw new Error("Permission Denied");
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(
        (body as { detail?: string }).detail ??
          `Request failed: ${response.statusText}`,
      );
    }

    return response.json() as Promise<T>;
  } catch (err) {
    // Keep the new 401/403 semantics intact (avoid wrapping them into a generic error).
    if (err instanceof Error && (err.message === "Permission Denied" || err.message === "Unauthorized")) {
      throw err;
    }
    throw err;
  }
}
