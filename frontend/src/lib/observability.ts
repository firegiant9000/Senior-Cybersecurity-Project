import * as Sentry from '@sentry/react'

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g
// KEEP IN SYNC with _SENSITIVE_KEY_PATTERNS in backend/app/core/observability.py.
// A backend test (test_observability_scrubber.py) asserts the two lists agree.
const SENSITIVE_KEY_PATTERNS = [
  'authorization',
  'cookie',
  'password',
  'secret',
  'token',
  'api_key',
  'apikey',
  'email',
  'hostname',
  'host_name',
]
const REDACTED = '[redacted]'

function scrub<T>(value: T, seen = new WeakSet<object>()): T {
  if (value === null || value === undefined) return value
  if (typeof value === 'string') {
    return value.replace(EMAIL_RE, REDACTED) as unknown as T
  }
  if (typeof value !== 'object') return value
  if (seen.has(value as object)) return value
  seen.add(value as object)

  if (Array.isArray(value)) {
    return value.map((v) => scrub(v, seen)) as unknown as T
  }
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    const lc = k.toLowerCase()
    if (SENSITIVE_KEY_PATTERNS.some((p) => lc.includes(p))) {
      out[k] = REDACTED
    } else {
      out[k] = scrub(v, seen)
    }
  }
  return out as unknown as T
}

export function initObservability(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
  if (!dsn) return

  Sentry.init({
    dsn,
    environment: (import.meta.env.VITE_SENTRY_ENVIRONMENT as string) || import.meta.env.MODE,
    release: (import.meta.env.VITE_SENTRY_RELEASE as string) || undefined,
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    sendDefaultPii: false,
    beforeSend(event) {
      try {
        return scrub(event)
      } catch {
        return null
      }
    },
  })
}
