/**
 * Authenticated fetch wrapper.
 * Automatically attaches the Firebase ID token as a Bearer header.
 */

import { auth } from "../firebase";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const user = auth.currentUser;
  const token = user ? await user.getIdToken() : null;

  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
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
