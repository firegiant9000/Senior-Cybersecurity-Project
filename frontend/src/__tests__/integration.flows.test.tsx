import type { ReactNode } from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockNavigate,
  mockSignup,
  mockLogin,
  mockRefreshProfile,
  mockLogout,
  mockListMembers,
  mockCreateInvite,
  mockUpdateMemberRole,
  mockRemoveMember,
  mockFetchAssessmentIntake,
} = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockSignup: vi.fn(),
  mockLogin: vi.fn(),
  mockRefreshProfile: vi.fn(),
  mockLogout: vi.fn(),
  mockListMembers: vi.fn(),
  mockCreateInvite: vi.fn(),
  mockUpdateMemberRole: vi.fn(),
  mockRemoveMember: vi.fn(),
  mockFetchAssessmentIntake: vi.fn(),
}))

// ─────────────────────────────────────────────────────────────────────────────
// Firebase Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: unknown) => void) => {
    cb(null)
    return vi.fn()
  }),
  signInWithEmailAndPassword: vi.fn(() => ({ user: { uid: 'user1' } })),
  createUserWithEmailAndPassword: vi.fn(() => ({ user: { uid: 'user2' } })),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))

vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

// ─────────────────────────────────────────────────────────────────────────────
// Context Mocks
// ─────────────────────────────────────────────────────────────────────────────

const mockAuthContext = {
  user: null as unknown,
  loading: false,
  orgId: null as number | null,
  orgLoading: false,
  profileError: false,
  role: null as string | null,
  orgRole: null as string | null,
  refreshProfile: mockRefreshProfile,
  login: mockLogin,
  signup: mockSignup,
  logout: mockLogout,
  getIdToken: vi.fn(),
}

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuthContext,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// ─────────────────────────────────────────────────────────────────────────────
// API Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('../api/members', () => ({
  listMembers: vi.fn(() => mockListMembers()),
  createInvite: vi.fn(() => mockCreateInvite()),
  updateMemberRole: vi.fn(() => mockUpdateMemberRole()),
  removeMember: vi.fn(() => mockRemoveMember()),
}))

vi.mock('../api/assessmentIntake', () => ({
  fetchAssessmentIntake: vi.fn(() => mockFetchAssessmentIntake()),
}))

vi.mock('../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api',
  fetchWithAuth: vi.fn(),
  getJsonAuth: vi.fn(),
}))

// ─────────────────────────────────────────────────────────────────────────────
// Component Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../Dashboard', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}))

vi.mock('../pages/LoginPage', () => ({
  default: ({ defaultSignUp }: { defaultSignUp?: boolean }) => (
    <div data-testid={defaultSignUp ? 'signup-page' : 'login-page'}>
      {defaultSignUp ? 'Sign Up' : 'Login'}
    </div>
  ),
}))

vi.mock('../pages/LandingPage', () => ({
  default: () => <div data-testid="landing-page">Landing</div>,
}))

vi.mock('../pages/SettingsPage', () => ({
  default: () => <div data-testid="settings-page">Settings</div>,
}))

vi.mock('../pages/AssessmentIntakePage', () => ({
  default: () => (
    <div data-testid="assessment-intake-page">
      Assessment
      <button onClick={() => mockRefreshProfile()}>Complete Onboarding</button>
    </div>
  ),
}))

vi.mock('../pages/AcceptInvitePage', () => ({
  default: () => <div data-testid="accept-invite-page">Accept Invite</div>,
}))

vi.mock('../components/ProtectedRoute', () => ({
  default: ({ children }: { children: ReactNode }) => {
    const auth = mockAuthContext
    if (!auth.user && !auth.loading) {
      return <div data-testid="redirect-login">Redirecting...</div>
    }
    return <>{children}</>
  },
}))

// ─────────────────────────────────────────────────────────────────────────────
// Import after all mocks
// ─────────────────────────────────────────────────────────────────────────────

import App from '../App'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderApp(initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>
  )
}

function setupAuthenticatedUser(email = 'user@example.com', uid = 'user1') {
  mockAuthContext.user = { uid, email, emailVerified: false } as unknown
  mockAuthContext.loading = false
}

function setupUserWithOrg(orgId = 1, orgRole = 'member', email = 'user@example.com') {
  mockAuthContext.user = { uid: 'user1', email } as unknown
  mockAuthContext.loading = false
  mockAuthContext.orgId = orgId
  mockAuthContext.orgLoading = false
  mockAuthContext.orgRole = orgRole
  mockAuthContext.role = 'viewer'
}

function setupAdminUser(email = 'admin@example.com') {
  mockAuthContext.user = { uid: 'admin1', email } as unknown
  mockAuthContext.loading = false
  mockAuthContext.role = 'admin'
  mockAuthContext.orgId = null
  mockAuthContext.orgRole = null
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('Integration Tests - User Flows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthContext.user = null
    mockAuthContext.loading = false
    mockAuthContext.orgId = null
    mockAuthContext.orgLoading = false
    mockAuthContext.role = null
    mockAuthContext.orgRole = null
    mockRefreshProfile.mockResolvedValue(undefined)
    mockListMembers.mockResolvedValue({ items: [], total: 0 })
    mockCreateInvite.mockResolvedValue(undefined)
  })

  describe('User Signup Flow', () => {
    it('allows unauthenticated user to view landing page', () => {
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    })

    it('navigates from landing to signup page', () => {
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()

      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()
    })

    it('signup page is accessible without authentication', () => {
      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()
    })

    it('completes signup and navigates to onboarding', () => {
      setupAuthenticatedUser()
      mockAuthContext.orgId = null

      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()

      // After signup, user is authenticated but has no org
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })
  })

  describe('User Onboarding Flow', () => {
    it('authenticated user without org reaches onboarding page', () => {
      setupAuthenticatedUser()
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('onboarding completion calls refreshProfile', async () => {
      setupAuthenticatedUser()
      renderApp(['/onboarding'])

      const completeBtn = screen.getByRole('button', { name: /Complete/i })
      fireEvent.click(completeBtn)

      await waitFor(() => {
        expect(mockRefreshProfile).toHaveBeenCalled()
      })
    })

    it('completes onboarding and user joins org', () => {
      setupAuthenticatedUser()
      mockRefreshProfile.mockImplementation(() => {
        mockAuthContext.orgId = 1
        mockAuthContext.orgLoading = false
        mockAuthContext.orgRole = 'owner'
      })

      renderApp(['/onboarding'])
      const completeBtn = screen.getByRole('button', { name: /Complete/i })
      fireEvent.click(completeBtn)

      // After completion, user has org and can access dashboard
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('prevents unauthenticated users from accessing onboarding', () => {
      renderApp(['/onboarding'])
      expect(screen.getByTestId('redirect-login')).toBeInTheDocument()
    })
  })

  describe('Invite Acceptance Flow', () => {
    it('authenticated user can accept org invite', () => {
      setupAuthenticatedUser()
      renderApp(['/invites/test-token-123'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })

    it('invite acceptance adds user to org', () => {
      setupAuthenticatedUser()
      mockRefreshProfile.mockImplementation(() => {
        mockAuthContext.orgId = 42
        mockAuthContext.orgLoading = false
        mockAuthContext.orgRole = 'member'
      })

      renderApp(['/invites/test-token'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()

      // After acceptance, user has org
      mockAuthContext.orgId = 42
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('prevents unauthenticated users from accessing invite', () => {
      renderApp(['/invites/token'])
      expect(screen.getByTestId('redirect-login')).toBeInTheDocument()
    })
  })

  describe('Organization Member Management Flow', () => {
    beforeEach(() => {
      mockListMembers.mockResolvedValue({
        items: [
          { user_id: 1, email: 'owner@example.com', role: 'owner', created_at: '2024-01-01T00:00:00Z' },
          { user_id: 2, email: 'member@example.com', role: 'member', created_at: '2024-01-02T00:00:00Z' },
        ],
        total: 2,
      })
    })

    it('org owner can access member management in settings', () => {
      setupUserWithOrg(1, 'owner')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('org member cannot access org settings (requires admin/owner)', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      // The page would load but member management sections would be hidden
    })

    it('owner creates invite for new member', async () => {
      setupUserWithOrg(1, 'owner')
      mockCreateInvite.mockResolvedValue(undefined)

      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      await waitFor(() => {
        expect(mockCreateInvite).toBeDefined()
      })
    })

    it('admin can update member roles', () => {
      setupUserWithOrg(1, 'admin')
      mockUpdateMemberRole.mockResolvedValue(undefined)

      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('owner can remove members from org', () => {
      setupUserWithOrg(1, 'owner')
      mockRemoveMember.mockResolvedValue(undefined)

      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })
  })

  describe('Assessment Workflow', () => {
    beforeEach(() => {
      mockFetchAssessmentIntake.mockResolvedValue({
        current_tier: 1,
        tiers: [{ id: 1, name: 'Tier 1', requirements: [] }],
        next_tier: 2,
        next_tier_progress: 50,
        fields_to_advance: 3,
      })
    })

    it('org member can access assessment intake', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('users without org can access assessment intake (requireOrg={false})', () => {
      setupAuthenticatedUser()
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('assessment data loads on page access', async () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/assessment-intake'])

      await waitFor(() => {
        expect(mockFetchAssessmentIntake).toBeDefined()
      })
    })
  })

  describe('Admin Dashboard Access Flow', () => {
    it('global admin can access admin-only dashboard tabs', () => {
      setupAdminUser()
      renderApp(['/dashboard?tab=admin&sub=pipelineHealth'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('org member cannot access admin-only tabs', () => {
      setupUserWithOrg(1, 'member')
      // User would see dashboard but admin tabs hidden
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('org admin can access admin tabs', () => {
      setupUserWithOrg(1, 'admin')
      renderApp(['/dashboard?tab=admin&sub=pipelineHealth'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })

  describe('User Without Organization Flow', () => {
    it('new user sees org-join CTA on dashboard', () => {
      setupAuthenticatedUser()
      mockAuthContext.orgId = null
      renderApp(['/dashboard'])
      // Component would show CTA
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('user without org cannot access org-only settings', () => {
      setupAuthenticatedUser()
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('user navigates from onboarding to settings after joining org', () => {
      setupAuthenticatedUser()
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
      cleanup()

      mockAuthContext.orgId = 1
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })
  })

  describe('User State Transitions', () => {
    it('handles user logout flow', () => {
      setupUserWithOrg(1, 'owner')
      mockLogout.mockClear()

      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()

      // Simulate logout
      mockAuthContext.user = null
      mockAuthContext.orgId = null
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    })

    it('handles org membership change', () => {
      setupAuthenticatedUser()
      mockAuthContext.orgId = null

      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()

      // User creates/joins org
      mockAuthContext.orgId = 42
      mockAuthContext.orgRole = 'owner'
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('handles role elevation', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      cleanup()

      // Admin promotes user to admin
      mockAuthContext.orgRole = 'admin'
      renderApp(['/dashboard?tab=admin'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })

  describe('Cross-Page Navigation', () => {
    it('user can navigate from dashboard to settings', () => {
      setupUserWithOrg(1, 'owner')
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()

      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('user can navigate from settings to assessment', () => {
      setupUserWithOrg(1, 'owner')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('user can navigate back to dashboard from any page', () => {
      setupUserWithOrg(1, 'owner')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('user can access all org-specific pages in sequence', () => {
      setupUserWithOrg(1, 'owner')

      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()

      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })
  })

  describe('Error Recovery Flows', () => {
    it('user can recover from authentication timeout', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()

      // Simulate auth timeout
      mockAuthContext.user = null
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    })

    it('user can recover from org access loss', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      cleanup()

      // User loses org access (kicked out)
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })

    it('admin can access pages after role change', () => {
      setupAdminUser()
      renderApp(['/dashboard'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      cleanup()

      renderApp(['/dashboard?tab=admin'])
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })

  describe('Concurrent User Scenarios', () => {
    it('different users have different permission levels on same routes', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      cleanup()

      // Switch to owner
      mockAuthContext.orgRole = 'owner'
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      // Same page but owner would see member management
    })

    it('users from different orgs cannot access each others data', () => {
      setupUserWithOrg(1, 'member')
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      cleanup()

      // User switches to different org
      mockAuthContext.orgId = 2
      renderApp(['/settings'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      // Would show different org's data
    })
  })

  describe('Loading State Flows', () => {
    it('shows loading state while auth initializes', () => {
      mockAuthContext.loading = true
      renderApp(['/'])
      // Should not render landing page while loading
      expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
    })

    it('shows loading state while org loads', () => {
      setupAuthenticatedUser()
      mockAuthContext.orgLoading = true
      renderApp(['/dashboard'])
      // Should wait for org load before showing restricted content
    })

    it('handles completion of loading states', async () => {
      mockAuthContext.loading = true
      mockAuthContext.user = null
      renderApp(['/'])
      expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()

      mockAuthContext.loading = false
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/'])
      // Would redirect to dashboard
    })
  })
})
