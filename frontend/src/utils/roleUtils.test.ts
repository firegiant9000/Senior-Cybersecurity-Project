import { describe, it, expect } from 'vitest'
import { isPlatformAdmin, isOrgAdmin } from './roleUtils'

describe('isPlatformAdmin', () => {
  it('is true for admin in any case', () => {
    expect(isPlatformAdmin('admin')).toBe(true)
    expect(isPlatformAdmin('Admin')).toBe(true)
  })

  it('is false for null, undefined, empty and other roles', () => {
    expect(isPlatformAdmin(null)).toBe(false)
    expect(isPlatformAdmin(undefined)).toBe(false)
    expect(isPlatformAdmin('')).toBe(false)
    expect(isPlatformAdmin('viewer')).toBe(false)
    expect(isPlatformAdmin('owner')).toBe(false)
  })
})

describe('isOrgAdmin', () => {
  it('is true for org owner and org admin', () => {
    expect(isOrgAdmin(null, 'owner')).toBe(true)
    expect(isOrgAdmin(null, 'admin')).toBe(true)
  })

  it('is true for a platform admin with no org role', () => {
    expect(isOrgAdmin('admin', null)).toBe(true)
  })

  it('is false for members and for no roles', () => {
    expect(isOrgAdmin(null, 'member')).toBe(false)
    expect(isOrgAdmin(null, null)).toBe(false)
    expect(isOrgAdmin(undefined, undefined)).toBe(false)
  })
})
