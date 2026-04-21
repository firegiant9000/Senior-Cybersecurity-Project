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

  it('returns false for undefined inputs (treated as non-admin)', () => {
    expect(canSeePipeline(undefined as unknown as null, undefined as unknown as null)).toBe(false)
  })

  it('returns false for whitespace-only role strings', () => {
    expect(canSeePipeline(' ', ' ')).toBe(false)
  })

  it('returns true for global admin regardless of orgRole value', () => {
    expect(canSeePipeline('admin', 'owner')).toBe(true)
    expect(canSeePipeline('admin', 'member')).toBe(true)
    expect(canSeePipeline('admin', '')).toBe(true)
  })

  it('returns true for org admin regardless of global role value', () => {
    expect(canSeePipeline('owner', 'admin')).toBe(true)
    expect(canSeePipeline('member', 'admin')).toBe(true)
    expect(canSeePipeline('', 'admin')).toBe(true)
  })

  it('returns false for all non-admin role combinations exhaustively', () => {
    const nonAdminRoles = ['viewer', 'owner', 'member', 'editor', null, ''] as const
    for (const role of nonAdminRoles) {
      for (const orgRole of nonAdminRoles) {
        expect(canSeePipeline(role, orgRole)).toBe(false)
      }
    }
  })
})

import { getVisibleGroups } from './roleUtils'
import type { TabGroupDef } from '../config/tabGroups'

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

  it('shows org-required groups as locked when orgId is null', () => {
    const result = getVisibleGroups([base, requiresOrg, requiresAdmin], {
      ...baseCtx,
      orgId: null,
    })
    expect(result.map((g) => g.id)).toEqual(['public', 'org-tab'])
    expect(result.find((g) => g.id === 'org-tab')?.locked).toBe(true)
  })

  it('shows org-required groups as locked while orgLoading is true', () => {
    const result = getVisibleGroups([base, requiresOrg], {
      ...baseCtx,
      orgId: 1,
      orgLoading: true,
    })
    expect(result.map((g) => g.id)).toEqual(['public', 'org-tab'])
    expect(result.find((g) => g.id === 'org-tab')?.locked).toBe(true)
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
