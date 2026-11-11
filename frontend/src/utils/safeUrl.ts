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
