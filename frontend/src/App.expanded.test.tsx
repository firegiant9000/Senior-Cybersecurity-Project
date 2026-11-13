import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { resetShellFocusForTests } from './components/shell/AppShell'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockNavigate,
  mockRefreshProfile,
} = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  const mockRefreshProfile = vi.fn()

  return {
    mockNavigate,
    mockRefreshProfile,
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// Firebase Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_auth: unknown, callback: (user: null) => void) => {
    callback(null)
    return vi.fn()
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
}))

// ─────────────────────────────────────────────────────────────────────────────
// Router Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// Component Mocks
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
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  getIdToken: vi.fn(),
}

vi.mock('./context/AuthContext.tsx', () => ({
  useAuth: () => mockAuthContext,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('./hooks/useDarkMode', () => ({
  useDarkMode: () => [false, vi.fn()],
}))

vi.mock('./pages/OverviewPage.tsx', () => ({
  default: () => <div data-testid="overview-page">Overview</div>,
}))

vi.mock('./pages/AssetsPage', () => ({
  default: () => <div data-testid="assets-page">Assets</div>,
}))

vi.mock('./pages/LoginPage.tsx', () => ({
  default: ({ defaultSignUp }: { defaultSignUp?: boolean }) => (
    <div data-testid={defaultSignUp ? 'signup-page' : 'login-page'}>
      {defaultSignUp ? 'Sign Up Page' : 'Login Page'}
    </div>
  ),
}))

vi.mock('./pages/LandingPage.tsx', () => ({
  default: () => <div data-testid="landing-page">Landing Page</div>,
}))

vi.mock('./pages/SettingsPage.tsx', () => ({
  default: () => <div data-testid="settings-page">Settings Page</div>,
}))

vi.mock('./pages/AssessmentDebugPage.tsx', () => ({
  default: () => <div data-testid="assessment-debug-page">Assessment Debug</div>,
}))

vi.mock('./pages/AssessmentIntakePage.tsx', () => ({
  default: () => (
    <div data-testid="assessment-intake-page">
      Assessment Intake
      <button onClick={() => mockRefreshProfile()}>Complete Onboarding</button>
    </div>
  ),
}))

vi.mock('./pages/OrgProfilePage.tsx', () => ({
  default: () => <div data-testid="org-profile-page">Org Profile</div>,
}))

vi.mock('./pages/AcceptInvitePage.tsx', () => ({
  default: () => <div data-testid="accept-invite-page">Accept Invite</div>,
}))

vi.mock('./pages/GlossaryPage.tsx', () => ({
  default: () => <div data-testid="glossary-page">Glossary</div>,
}))

vi.mock('./pages/ExecutiveReportPage.tsx', () => ({
  default: () => <div data-testid="executive-report-page">Executive Report</div>,
}))

vi.mock('./components/ProtectedRoute.tsx', () => ({
  default: ({ children, requireOrg = true }: { children: React.ReactNode; requireOrg?: boolean }) => {
    const authContext = mockAuthContext
    if (!authContext.user && !authContext.loading) {
      return <div data-testid="protected-redirect">Redirecting to login...</div>
    }
    if (requireOrg && authContext.orgLoading) {
      return <div data-testid="org-loading">Loading org...</div>
    }
    if (requireOrg && !authContext.orgId) {
      return <div data-testid="org-redirect">Redirecting to onboarding...</div>
    }
    return <>{children}</>
  },
}))

// Import after all mocks
import App from './App'

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

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('App - Routing & Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetShellFocusForTests()
    mockAuthContext.user = null
    mockAuthContext.loading = false
    mockAuthContext.orgId = null
    mockAuthContext.orgLoading = false
    mockAuthContext.role = null
    mockAuthContext.orgRole = null
  })

  describe('Root Route (/)', () => {
    it('shows landing page when user is not authenticated', () => {
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    })

    it('shows landing page while auth is loading', () => {
      mockAuthContext.loading = true
      renderApp(['/'])
      expect(screen.queryByTestId('overview-page')).not.toBeInTheDocument()
    })

    it('redirects to the overview when user is authenticated', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('does not render content while auth is loading and user exists', () => {
      mockAuthContext.loading = true
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/'])
      expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
      expect(screen.queryByTestId('overview-page')).not.toBeInTheDocument()
    })
  })

  describe('Login Route (/login)', () => {
    it('shows login page at /login', () => {
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    it('login page does not have defaultSignUp flag', () => {
      renderApp(['/login'])
      expect(screen.queryByTestId('signup-page')).not.toBeInTheDocument()
    })

    it('allows unauthenticated access to login', () => {
      mockAuthContext.user = null
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    it('is accessible regardless of org status', () => {
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })
  })

  describe('Signup Route (/signup)', () => {
    it('shows signup page at /signup', () => {
      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()
    })

    it('signup page has defaultSignUp flag set to true', () => {
      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()
    })

    it('allows unauthenticated access to signup', () => {
      mockAuthContext.user = null
      renderApp(['/signup'])
      expect(screen.getByTestId('signup-page')).toBeInTheDocument()
    })
  })

  describe('Onboarding Route (/onboarding)', () => {
    it('shows onboarding page when user is authenticated', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('allows onboarding without requiring org (requireOrg={false})', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('redirects unauthenticated users from onboarding', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/onboarding'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('calls refreshProfile on onboarding completion', async () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/onboarding'])

      const completeButton = screen.getByRole('button', { name: /Complete Onboarding/i })
      fireEvent.click(completeButton)

      await waitFor(() => {
        expect(mockRefreshProfile).toHaveBeenCalled()
      })
    })
  })

  describe('Invite Accept Route (/invites/:token)', () => {
    it('shows invite page when user is authenticated', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/invites/test-token-123'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })

    it('allows invite access without requiring org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/invites/test-token-123'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })

    it('redirects unauthenticated users from invite page', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/invites/test-token-123'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('passes token in URL to invite component', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/invites/abc123xyz789'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })
  })

  describe('Settings Route (/settings/account)', () => {
    it('shows settings page when user is authenticated', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('requires authentication to access settings', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/settings/account'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('requires org to access settings (ProtectedRoute default)', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/settings/account'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })

    it('allows access when user and org are both present', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 42
      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })
  })

  describe('Assessment Debug Route (/admin/assessment-debug, legacy /settings/assessment-debug)', () => {
    it('shows assessment debug page to a platform admin with an org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      mockAuthContext.role = 'admin'
      renderApp(['/admin/assessment-debug'])
      expect(screen.getByTestId('assessment-debug-page')).toBeInTheDocument()
    })

    it('redirects the legacy URL to the admin path', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      mockAuthContext.role = 'admin'
      renderApp(['/settings/assessment-debug'])
      expect(screen.getByTestId('assessment-debug-page')).toBeInTheDocument()
    })

    it('shows not found to a user who is not a platform admin', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/settings/assessment-debug'])
      expect(screen.queryByTestId('assessment-debug-page')).not.toBeInTheDocument()
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('requires authentication', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/admin/assessment-debug'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('requires org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/admin/assessment-debug'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })
  })

  describe('Assessment Intake Route (legacy /assessment-intake redirects to /onboarding)', () => {
    it('shows assessment intake page when authenticated and has org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('requires authentication', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('does not require org (requireOrg={false})', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })
  })

  describe('Organization Profile Route (/settings/organisation, legacy /org-profile)', () => {
    it('redirects the legacy /org-profile URL to the organisation page', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/org-profile'])
      expect(screen.getByTestId('org-profile-page')).toBeInTheDocument()
    })

    it('shows org profile page when authenticated and has org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/settings/organisation'])
      expect(screen.getByTestId('org-profile-page')).toBeInTheDocument()
    })

    it('requires authentication', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/settings/organisation'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('requires org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/settings/organisation'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })
  })

  describe('Overview and catch-all routes', () => {
    it('shows the overview for authenticated users at /overview', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('redirects the legacy /dashboard URL to the overview', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/dashboard'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('renders the overview inside the shell main landmark (id="main")', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/overview'])
      const main = document.getElementById('main')
      expect(main).not.toBeNull()
      expect(main).toContainElement(screen.getByTestId('overview-page'))
    })

    it('renders no shell header or main landmark for a signed-out user at /overview', () => {
      renderApp(['/overview'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
      expect(document.getElementById('main')).toBeNull()
      expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    })

    it('shows the not-found page, not the overview, at undefined routes', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/unknown-route'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
      expect(screen.queryByTestId('overview-page')).not.toBeInTheDocument()
    })

    it('shows the not-found page at /dashboard/inventory', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/dashboard/inventory'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('shows the not-found page at /nope', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/nope'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('shows the not-found page when signed out (no guard)', () => {
      renderApp(['/nope'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
      expect(screen.queryByTestId('protected-redirect')).not.toBeInTheDocument()
    })

    it('redirects /assessment-intake to the onboarding page', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('redirects the legacy /assets URL to the assets page', async () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/assets'])
      expect(await screen.findByTestId('assets-page')).toBeInTheDocument()
    })

    it('requires authentication to access the overview', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/overview'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('requires org to access the overview', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/overview'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })

    it('shows the overview when user and org both present', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })
  })

  describe('Shell membership', () => {
    it('renders /glossary inside #main for a user with no organisation', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/glossary'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('glossary-page'))
    })

    it('renders /onboarding and /invites/:token inside #main without an organisation', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/onboarding'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('assessment-intake-page'))
      cleanup()
      renderApp(['/invites/tok'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('accept-invite-page'))
    })

    it('renders /settings/account inside #main', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/settings/account'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('settings-page'))
    })

    it('renders /settings/organisation and /admin/assessment-debug inside #main', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      mockAuthContext.role = 'admin'
      renderApp(['/settings/organisation'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('org-profile-page'))
      cleanup()
      renderApp(['/admin/assessment-debug'])
      expect(document.getElementById('main')).toContainElement(screen.getByTestId('assessment-debug-page'))
    })

    it('keeps /org/report outside the shell', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/org/report'])
      expect(screen.getByTestId('executive-report-page')).toBeInTheDocument()
      expect(document.getElementById('main')).toBeNull()
    })

    it('keeps /login outside the shell', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
      expect(document.getElementById('main')).toBeNull()
    })

    it('still guards moved routes: signed-out user sees no shell', () => {
      renderApp(['/glossary'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
      expect(document.getElementById('main')).toBeNull()
    })

    it('still requires an organisation for /settings/account', () => {
      mockAuthContext.user = { uid: 'user1', email: 'user@example.com' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/settings/account'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
      expect(document.getElementById('main')).toBeNull()
    })
  })

  describe('Protected Routes', () => {
    it('blocks unauthenticated users from protected routes', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/settings/account'])
      expect(screen.getByTestId('protected-redirect')).toBeInTheDocument()
    })

    it('blocks users without org from org-required routes', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/overview'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })

    it('allows onboarding and invite routes without org requirement', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('waits for org loading before redirecting', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = true
      renderApp(['/overview'])
      expect(screen.queryByTestId('org-redirect')).not.toBeInTheDocument()
    })

    it('waits for auth loading before redirecting', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = true
      renderApp(['/settings/account'])
      expect(screen.queryByTestId('protected-redirect')).not.toBeInTheDocument()
    })
  })

  describe('Route Navigation Flows', () => {
    it('supports navigation from login to onboarding', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()

      mockAuthContext.orgId = 1
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })

    it('supports navigation from onboarding to the overview', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()

      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('supports navigation from invite to settings', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/invites/token123'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()

      mockAuthContext.orgId = 1
      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('supports navigation from the overview to settings', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()

      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
    })

    it('supports navigation from settings to assessment pages', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      renderApp(['/assessment-intake'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('does not render content while auth is loading at root', () => {
      mockAuthContext.loading = true
      renderApp(['/'])
      expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
      expect(screen.queryByTestId('overview-page')).not.toBeInTheDocument()
    })

    it('does not render content while org is loading for protected routes', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = true
      renderApp(['/overview'])
      expect(screen.queryByTestId('org-redirect')).not.toBeInTheDocument()
      expect(screen.queryByTestId('overview-page')).not.toBeInTheDocument()
    })
  })

  describe('User Status Changes', () => {
    it('handles user logging in', () => {
      mockAuthContext.user = null
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()

      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('handles user joining org after creation', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      renderApp(['/onboarding'])
      expect(screen.getByTestId('assessment-intake-page')).toBeInTheDocument()

      mockAuthContext.orgId = 42
      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })

    it('handles user leaving org', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()

      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/overview'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })
  })

  describe('Route Parameter Handling', () => {
    it('preserves token parameter in invite route', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/invites/special-token-abc123'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })

    it('handles long token values', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      const longToken = 'a'.repeat(1000)
      renderApp([`/invites/${longToken}`])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })

    it('handles special characters in tokens', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      renderApp(['/invites/token-with-special-chars_!@#$%'])
      expect(screen.getByTestId('accept-invite-page')).toBeInTheDocument()
    })
  })

  describe('App Rendering', () => {
    it('renders App component without errors', () => {
      renderApp(['/'])
      expect(document.body).toBeTruthy()
    })

    it('maintains route structure during rendering', () => {
      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    it('handles multiple route changes', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1

      renderApp(['/login'])
      expect(screen.getByTestId('login-page')).toBeInTheDocument()

      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()

      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles null user gracefully', () => {
      mockAuthContext.user = null
      mockAuthContext.loading = false
      renderApp(['/'])
      expect(screen.getByTestId('landing-page')).toBeInTheDocument()
    })

    it('handles missing orgId gracefully', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = null
      mockAuthContext.orgLoading = false
      renderApp(['/settings/account'])
      expect(screen.getByTestId('org-redirect')).toBeInTheDocument()
    })

    it('shows the not-found page for an invalid route', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1
      renderApp(['/completely-invalid-route'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('handles rapid route changes', () => {
      mockAuthContext.user = { uid: 'user1' } as unknown
      mockAuthContext.orgId = 1

      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
      cleanup()

      renderApp(['/settings/account'])
      expect(screen.getByTestId('settings-page')).toBeInTheDocument()
      cleanup()

      renderApp(['/overview'])
      expect(screen.getByTestId('overview-page')).toBeInTheDocument()
    })
  })
})
