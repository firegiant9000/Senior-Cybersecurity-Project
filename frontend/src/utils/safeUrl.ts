/**
 * Returns the normalised URL when `value` (trimmed) is an absolute http(s) URL,
 * otherwise null. Use before putting user-typed text into `src`/`href`.
 */
export function httpUrlOrNull(value: string): string | null {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

/**
 * Returns `value` unchanged when it is a same-origin app path safe to redirect to after sign-in,
 * otherwise null. Rejects anything that is not a path (`//host`, `/\host`, absolute URLs),
 * any control character, and the auth pages themselves (`/login`, `/signup`) to avoid loops.
 * The value must already be decoded once by the caller (e.g. via URLSearchParams); not decoded here.
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (typeof value !== "string" || !value.startsWith("/")) return null;
  if (value[1] === "/" || value[1] === "\\") return null;
  for (let i = 0; i < value.length; i++) {
    if (value.charCodeAt(i) < 0x20) return null;
  }
  const path = value.split(/[?#]/, 1)[0];
  if (path === "/login" || path === "/signup") return null;
  return value;
}
