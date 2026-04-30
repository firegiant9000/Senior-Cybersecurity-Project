/**
 * Test Utilities & Helpers
 * 
 * Centralized test setup, factories, and custom render functions
 * for consistent and maintainable test code across the project.
 */

import { render, RenderOptions, RenderResult } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import React from 'react'
import { vi, expect } from 'vitest'

import type { OrgInvite, OrgMember } from '../api/members'

// ─────────────────────────────────────────────────────────────────────────────
// Mock Data Factories
// ─────────────────────────────────────────────────────────────────────────────

export interface MockUser {
  uid: string
  email: string
  emailVerified: boolean
  metadata?: { lastSignInTime: string }
}

// MockOrgMember / MockInvite are aliases for the real API types so the
// compiler enforces alignment between mocks and the schemas the components
// actually consume. See frontend/src/api/members.ts for the source of truth
// (which mirrors backend/app/schemas/org_invite.py).
export type MockOrgMember = OrgMember
export type MockInvite = OrgInvite

export interface MockAssessmentData {
  current_tier: number
  tiers: Array<{ id: number; name: string; requirements: string[] }>
  next_tier: number | null
  next_tier_progress: number
  fields_to_advance: number
}

/**
 * Factory function to create mock user objects
 */
export function createMockUser(overrides: Partial<MockUser> = {}): MockUser {
  return {
    uid: 'test-user-' + Math.random().toString(36).substr(2, 9),
    email: 'user@example.com',
    emailVerified: false,
    metadata: { lastSignInTime: '2024-01-01T00:00:00Z' },
    ...overrides,
  }
}

/**
 * Factory function to create mock organization members
 */
export function createMockOrgMember(overrides: Partial<MockOrgMember> = {}): MockOrgMember {
  return {
    user_id: Math.floor(Math.random() * 10000),
    email: `user-${Math.random().toString(36).substr(2, 5)}@example.com`,
    role: 'member',
    is_active: true,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Factory function to create mock invitation objects
 */
export function createMockInvite(overrides: Partial<MockInvite> = {}): MockInvite {
  const createdAt = new Date()
  const expiresAt = new Date(createdAt.getTime() + 30 * 24 * 60 * 60 * 1000) // 30 days later

  return {
    id: Math.floor(Math.random() * 10000),
    org_id: 1,
    email: `invited-${Math.random().toString(36).substr(2, 5)}@example.com`,
    role: 'member',
    status: 'pending',
    inviter_id: null,
    created_at: createdAt.toISOString(),
    expires_at: expiresAt.toISOString(),
    ...overrides,
  }
}

/**
 * Factory function to create mock assessment data
 */
export function createMockAssessmentData(overrides: Partial<MockAssessmentData> = {}): MockAssessmentData {
  return {
    current_tier: 1,
    tiers: [
      { id: 1, name: 'Foundation', requirements: ['requirement1', 'requirement2'] },
      { id: 2, name: 'Intermediate', requirements: ['requirement3', 'requirement4'] },
      { id: 3, name: 'Advanced', requirements: ['requirement5', 'requirement6'] },
    ],
    next_tier: 2,
    next_tier_progress: 50,
    fields_to_advance: 3,
    ...overrides,
  }
}

/**
 * Factory function to create mock members list response
 */
export function createMockMembersList(count = 3): { items: MockOrgMember[]; total: number } {
  return {
    items: Array.from({ length: count }, (_, i) =>
      createMockOrgMember({
        user_id: i + 1,
        email: `member${i + 1}@example.com`,
        role: i === 0 ? 'owner' : i === 1 ? 'admin' : 'member',
      }),
    ),
    total: count,
  }
}

/**
 * Factory function to create mock invites list response
 */
export function createMockInvitesList(count = 2): { items: MockInvite[]; total: number } {
  return {
    items: Array.from({ length: count }, (_, i) =>
      createMockInvite({
        id: i + 1,
        email: `pending${i + 1}@example.com`,
        role: i % 2 === 0 ? 'member' : 'admin',
      }),
    ),
    total: count,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Custom Render Functions
// ─────────────────────────────────────────────────────────────────────────────

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: MemoryRouterProps['initialEntries']
  initialIndex?: MemoryRouterProps['initialIndex']
  authContext?: Partial<Record<string, unknown>>
}

/**
 * Custom render function that wraps components with MemoryRouter
 * Use this for components that need React Router functionality
 */
export function renderWithRouter(
  ui: React.ReactElement,
  {
    initialEntries = ['/'],
    initialIndex = 0,
    ...renderOptions
  }: CustomRenderOptions = {},
): RenderResult {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
        {children}
      </MemoryRouter>
    )
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}

/**
 * Create a fully setup test environment with all providers and mocks
 * Returns both the render result and mock functions for assertions
 */
export function setupTestEnvironment() {
  const mockAuth = {
    user: createMockUser(),
    loading: false,
    orgId: null as number | null,
    orgLoading: false,
    profileError: false,
    role: null as string | null,
    orgRole: null as string | null,
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
  }

  const mockApis = {
    listMembers: vi.fn(() => Promise.resolve(createMockMembersList())),
    listInvites: vi.fn(() => Promise.resolve(createMockInvitesList())),
    createInvite: vi.fn(() => Promise.resolve(undefined)),
    revokeInvite: vi.fn(() => Promise.resolve(undefined)),
    updateMemberRole: vi.fn(() => Promise.resolve(undefined)),
    removeMember: vi.fn(() => Promise.resolve(undefined)),
    fetchAssessmentIntake: vi.fn(() => Promise.resolve(createMockAssessmentData())),
    fetchAssessmentDebug: vi.fn(() => Promise.resolve({})),
    fetchAISummaryHistory: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  }

  const mockNavigation = {
    navigate: vi.fn(),
    pathname: '/',
  }

  return {
    mockAuth,
    mockApis,
    mockNavigation,
    clearMocks: () => {
      Object.values(mockAuth).forEach(v => {
        if (typeof v === 'function' && v.mockClear) v.mockClear()
      })
      Object.values(mockApis).forEach(v => {
        if (typeof v === 'function' && v.mockClear) v.mockClear()
      })
      Object.values(mockNavigation).forEach(v => {
        if (typeof v === 'function' && v.mockClear) v.mockClear()
      })
    },
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth Context Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create mock auth context value for an unauthenticated user
 */
export function createUnauthenticatedAuth() {
  return {
    user: null,
    loading: false,
    orgId: null,
    orgLoading: false,
    profileError: false,
    role: null,
    orgRole: null,
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
  }
}

/**
 * Create mock auth context value for an authenticated user without org
 */
export function createAuthenticatedAuth(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    user: createMockUser(),
    loading: false,
    orgId: null,
    orgLoading: false,
    profileError: false,
    role: null,
    orgRole: null,
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
    ...overrides,
  }
}

/**
 * Create mock auth context value for user with organization membership
 */
export function createOrgMemberAuth(orgId = 1, orgRole: string = 'member', overrides: Partial<Record<string, unknown>> = {}) {
  return {
    user: createMockUser(),
    loading: false,
    orgId,
    orgLoading: false,
    profileError: false,
    role: 'viewer',
    orgRole,
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
    ...overrides,
  }
}

/**
 * Create mock auth context value for global admin
 */
export function createAdminAuth(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    user: createMockUser({ email: 'admin@example.com' }),
    loading: false,
    orgId: null,
    orgLoading: false,
    profileError: false,
    role: 'admin',
    orgRole: null,
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
    ...overrides,
  }
}

/**
 * Create mock auth context value for org admin
 */
export function createOrgAdminAuth(orgId = 1, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    user: createMockUser(),
    loading: false,
    orgId,
    orgLoading: false,
    profileError: false,
    role: 'viewer',
    orgRole: 'admin',
    logout: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    refreshProfile: vi.fn(),
    getIdToken: vi.fn(),
    ...overrides,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// API Mock Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Setup realistic member list API response
 */
export function mockMembersAPI(mockFn: { mockResolvedValue: (v: unknown) => void }, count = 3) {
  const membersList = createMockMembersList(count)
  mockFn.mockResolvedValue(membersList)
  return membersList
}

/**
 * Setup realistic invites API response
 */
export function mockInvitesAPI(mockFn: { mockResolvedValue: (v: unknown) => void }, count = 2) {
  const invitesList = createMockInvitesList(count)
  mockFn.mockResolvedValue(invitesList)
  return invitesList
}

/**
 * Setup assessment intake API with typical response
 */
export function mockAssessmentAPI(mockFn: { mockResolvedValue: (v: unknown) => void }, tierNumber = 1) {
  const data = createMockAssessmentData({ current_tier: tierNumber })
  mockFn.mockResolvedValue(data)
  return data
}

/**
 * Setup API to simulate error response
 */
export function mockAPIError(mockFn: { mockRejectedValue: (v: unknown) => void }, errorMessage = 'Network error') {
  mockFn.mockRejectedValue(new Error(errorMessage))
}

// ─────────────────────────────────────────────────────────────────────────────
// Common Test Data Builders
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create a complete set of mock org data
 */
export function createCompleteOrgData(orgId = 1) {
  return {
    orgId,
    members: createMockMembersList(5),
    invites: createMockInvitesList(3),
    assessment: createMockAssessmentData(),
  }
}

/**
 * Create test user scenarios for role-based testing
 */
export function createRoleScenarios(orgId = 1) {
  return {
    owner: createOrgMemberAuth(orgId, 'owner'),
    admin: createOrgAdminAuth(orgId),
    member: createOrgMemberAuth(orgId, 'member'),
    viewer: createOrgMemberAuth(orgId, 'viewer'),
    globalAdmin: createAdminAuth(),
  }
}

/**
 * Create different org membership states
 */
export function createOrgStates() {
  return {
    noOrg: createAuthenticatedAuth(),
    pendingOrgLoad: {
      ...createAuthenticatedAuth(),
      orgLoading: true,
    },
    orgMember: createOrgMemberAuth(1, 'member'),
    orgOwner: createOrgMemberAuth(1, 'owner'),
    multipleOrgs: {
      current: createOrgMemberAuth(1, 'member'),
      switchTo: (orgId: number) => createOrgMemberAuth(orgId, 'member'),
    },
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Assertion Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Assert that API was called with expected parameters
 */
export function expectAPICall(mockFn: { mock: { calls: unknown[][] } }, expectedArgs: unknown, callIndex = 0) {
  expect(mockFn).toHaveBeenCalled()
  expect(mockFn.mock.calls[callIndex]).toEqual(expectedArgs)
}

/**
 * Assert that a list of APIs were all called
 */
export function expectAPIsCalledInOrder(mocks: unknown[]) {
  mocks.forEach(mock => {
    expect(mock).toHaveBeenCalled()
  })
}

/**
 * Assert that user has required role for action
 */
export function expectRequiresRole(role: string | string[]) {
  const roles = Array.isArray(role) ? role : [role]
  return {
    validateUser: (userRole: string) => {
      expect(roles).toContain(userRole)
    },
  }
}

/**
 * Assert that user requires org membership
 */
export function expectRequiresOrg(authContext: { orgId: number | null | undefined }) {
  expect(authContext.orgId).not.toBeNull()
  expect(authContext.orgId).not.toBe(undefined)
}

// ─────────────────────────────────────────────────────────────────────────────
// Test Setup Utilities
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create standardized test setup for page components
 */
export function createPageTestSetup(options: {
  auth?: unknown
  route?: string
  apis?: unknown
} = {}) {
  const auth = options.auth || createOrgMemberAuth(1, 'owner')
  const apis = options.apis || setupTestEnvironment().mockApis

  return {
    auth,
    apis,
    route: options.route || '/',
    render: (component: React.ReactElement) => {
      return renderWithRouter(component, { initialEntries: [options.route || '/'] })
    },
  }
}

/**
 * Create mock search params for testing
 */
export function createMockSearchParams(params: Record<string, string>) {
  const sp = new URLSearchParams(params)
  return {
    get: (key: string) => sp.get(key),
    entries: () => sp.entries(),
    toString: () => sp.toString(),
  }
}

/**
 * Simulate time passage in tests
 */
export async function advanceTime(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Create mock localStorage for testing
 */
export function createMockStorage() {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Export summary of utilities
// ─────────────────────────────────────────────────────────────────────────────

export const TestUtilities = {
  // Factories
  createMockUser,
  createMockOrgMember,
  createMockInvite,
  createMockAssessmentData,
  createMockMembersList,
  createMockInvitesList,

  // Render functions
  renderWithRouter,
  setupTestEnvironment,

  // Auth helpers
  createUnauthenticatedAuth,
  createAuthenticatedAuth,
  createOrgMemberAuth,
  createAdminAuth,
  createOrgAdminAuth,

  // API helpers
  mockMembersAPI,
  mockInvitesAPI,
  mockAssessmentAPI,
  mockAPIError,

  // Data builders
  createCompleteOrgData,
  createRoleScenarios,
  createOrgStates,

  // Assertions
  expectAPICall,
  expectAPIsCalledInOrder,
  expectRequiresRole,
  expectRequiresOrg,

  // Setup utilities
  createPageTestSetup,
  createMockSearchParams,
  advanceTime,
  createMockStorage,
}

export default TestUtilities
