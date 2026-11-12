import { describe, it, expect } from 'vitest'
import { isPlatformAdmin, isOrgAdmin, getVisibleGroups } from './roleUtils'
import type { TabGroupDef } from '../config/tabGroups'

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

describe('getVisibleGroups', () => {
  const base: TabGroupDef = { id: 'public', label: 'Public' }
  const requiresOrg: TabGroupDef = { id: 'org-tab', label: 'Org', requiresOrg: true }
  const requiresAdmin: TabGroupDef = { id: 'admin-tab', label: 'Admin', requiresAdmin: true }
  const requiresBoth: TabGroupDef = { id: 'both-tab', label: 'Both', requiresOrg: true, requiresAdmin: true }

  const baseCtx = { orgId: 1, role: null, orgRole: null, orgLoading: false }

  it('shows all groups to global admin with org', () => {
    const result = getVisibleGroups([base, requiresOrg, requiresAdmin, requiresBoth], {
      ...baseCtx,
      role: 'admin',
    })
    expect(result.map((g) => g.id)).toEqual(['public', 'org-tab', 'admin-tab', 'both-tab'])
  })

  it('hides admin groups from non-admin users', () => {
    const result = getVisibleGroups([base, requiresOrg, requiresAdmin, requiresBoth], baseCtx)
    expect(result.map((g) => g.id)).toEqual(['public', 'org-tab'])
  })

  it('hides the admin group from an org admin who is not a platform admin', () => {
    const result = getVisibleGroups([base, requiresAdmin], {
      ...baseCtx,
      role: null,
      orgRole: 'admin',
    })
    expect(result.map((g) => g.id)).toEqual(['public'])
  })

  it('omits org-required groups when orgId is null', () => {
    const result = getVisibleGroups([base, requiresOrg, requiresAdmin], {
      ...baseCtx,
      orgId: null,
    })
    expect(result.map((g) => g.id)).toEqual(['public'])
  })

  it('omits org-required groups while orgLoading is true', () => {
    const result = getVisibleGroups([base, requiresOrg], {
      ...baseCtx,
      orgId: 1,
      orgLoading: true,
    })
    expect(result.map((g) => g.id)).toEqual(['public'])
  })

  it('returns empty array when no groups pass filters', () => {
    const result = getVisibleGroups([requiresAdmin, requiresBoth], baseCtx)
    expect(result).toHaveLength(0)
  })

  it('returns empty array when input is empty', () => {
    expect(getVisibleGroups([], baseCtx)).toEqual([])
  })

  it('filters subTabs by admin requirement and removes group when all subTabs are hidden', () => {
    const group: TabGroupDef = {
      id: 'group',
      label: 'Group',
      subTabs: [{ id: 'sub-admin', label: 'Admin Sub', requiresAdmin: true }],
    }
    const result = getVisibleGroups([group], baseCtx)
    expect(result).toHaveLength(0)
  })

  it('keeps group when at least one subTab is visible', () => {
    const group: TabGroupDef = {
      id: 'group',
      label: 'Group',
      subTabs: [
        { id: 'sub-public', label: 'Public Sub' },
        { id: 'sub-admin', label: 'Admin Sub', requiresAdmin: true },
      ],
    }
    const result = getVisibleGroups([group], baseCtx)
    expect(result).toHaveLength(1)
    expect(result[0].subTabs?.map((s) => s.id)).toEqual(['sub-public'])
  })
})
