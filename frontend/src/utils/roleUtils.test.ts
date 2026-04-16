import { describe, it, expect } from 'vitest'
import { canSeePipeline } from './roleUtils'

describe('canSeePipeline', () => {
  it('returns true for global admin', () => {
    expect(canSeePipeline('admin', null)).toBe(true)
  })

  it('returns true for org admin', () => {
    expect(canSeePipeline('viewer', 'admin')).toBe(true)
  })

  it('returns true when both are admin', () => {
    expect(canSeePipeline('admin', 'admin')).toBe(true)
  })

  it('returns false for org owner (not admin)', () => {
    expect(canSeePipeline('viewer', 'owner')).toBe(false)
  })

  it('returns false for org member', () => {
    expect(canSeePipeline('viewer', 'member')).toBe(false)
  })

  it('returns false when both are null', () => {
    expect(canSeePipeline(null, null)).toBe(false)
  })

  it('returns false for empty-string roles', () => {
    expect(canSeePipeline('', '')).toBe(false)
  })

  it('is case-sensitive (uppercase Admin does not match)', () => {
    // Backend values are normalized to lowercase before reaching this function.
    // This test documents that the function itself does NOT case-fold.
    expect(canSeePipeline('Admin', null)).toBe(false)
  })
})
