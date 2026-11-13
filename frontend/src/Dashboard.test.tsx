import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// --- Firebase mocks ---
vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: null) => void) => { cb(null); return vi.fn(); }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))
vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

// --- AuthContext mock — overridden per test ---
const mockAuthValues = {
  user: { uid: 'u1', email: 'test@example.com' } as unknown,
  loading: false,
  orgId: null as number | null,
  orgLoading: false,
  profileError: false,
  role: null as string | null,
  orgRole: null as string | null,
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  getIdToken: vi.fn(),
  refreshProfile: vi.fn(),
}

vi.mock('./context/AuthContext', () => ({
  useAuth: () => mockAuthValues,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// --- Heavy component mocks ---
vi.mock('./hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: {
      summary: null, geographicThreats: [], attackTypes: [], severityDistribution: [],
      temporalTrends: [], sectorAttackMatrix: [], industryRisk: [], kevTotal: 0,
      lossProjection: null, executiveSummary: null,
    },
    loading: false, loadingHeavy: false, errors: [], lastUpdated: null, refresh: vi.fn(),
  }),
}))
vi.mock('./hooks/useDarkMode', () => ({ useDarkMode: () => [false, vi.fn()] }))
vi.mock('./components/dashboard/OverviewTab', () => ({ default: () => <div>Overview</div> }))
vi.mock('./components/dashboard/DashboardHeader', () => ({ default: () => <div>Header</div> }))
vi.mock('./pages/NotFoundPage', () => ({ default: () => <div data-testid="not-found-page">Not found</div> }))
vi.mock('./components/tabs/SmBAdvisorTab', () => ({ default: () => <div data-testid="tab-smbAdvisor">SMB</div> }))
vi.mock('./components/tabs/FindingsTab', () => ({ default: () => <div data-testid="tab-findings">Findings</div> }))
vi.mock('./components/tabs/AISummaryTab', () => ({ default: () => <div data-testid="tab-aiSummary">AI</div> }))
vi.mock('./components/tabs/VendorAlertsTab', () => ({ default: () => <div data-testid="tab-vendorAlerts">Vendor</div> }))
vi.mock('./components/tabs/PipelineHealthTab', () => ({ default: () => <div data-testid="tab-pipelineHealth">Pipeline</div> }))
vi.mock('./api/fetchWithAuth', () => ({ API_BASE_URL: '', fetchWithAuth: vi.fn(), getJsonAuth: vi.fn() }))
vi.mock('./components/shared/WidgetSkeleton', () => ({ default: () => null }))

import Dashboard from './Dashboard'

function renderDashboard(url = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Dashboard />
    </MemoryRouter>
  )
}

describe('Dashboard tab filtering', () => {
  beforeEach(() => {
    mockAuthValues.orgId = null
    mockAuthValues.orgLoading = false
    mockAuthValues.role = null
    mockAuthValues.orgRole = null
  })

  it.each(['smbAdvisor', 'findings', 'aiSummary', 'vendorAlerts'])(
    'renders not-found for org-only %s when user has no org',
    (tab) => {
      renderDashboard(`/dashboard?tab=${tab}`)
      expect(screen.getByTestId('not-found-page')).toBeTruthy()
      expect(screen.queryByTestId(`tab-${tab}`)).toBeNull()
    },
  )

  it.each(['smbAdvisor', 'findings', 'aiSummary', 'vendorAlerts'])(
    'renders org-only %s when user has an org',
    async (tab) => {
      mockAuthValues.orgId = 42
      renderDashboard(`/dashboard?tab=${tab}`)
      expect(await screen.findByTestId(`tab-${tab}`)).toBeTruthy()
    },
  )

  it('renders not-found for pipelineHealth for a regular org member', () => {
    mockAuthValues.orgId = 42
    mockAuthValues.role = 'viewer'
    mockAuthValues.orgRole = 'member'
    renderDashboard('/dashboard?tab=pipelineHealth')
    expect(screen.getByTestId('not-found-page')).toBeTruthy()
    expect(screen.queryByTestId('tab-pipelineHealth')).toBeNull()
  })

  it('renders pipelineHealth for a global admin', async () => {
    mockAuthValues.role = 'admin'
    mockAuthValues.orgRole = null
    renderDashboard('/dashboard?tab=pipelineHealth')
    expect(await screen.findByTestId('tab-pipelineHealth')).toBeTruthy()
  })

  it('renders not-found for pipelineHealth for an org admin who is not a platform admin', () => {
    mockAuthValues.orgId = 42
    mockAuthValues.role = 'viewer'
    mockAuthValues.orgRole = 'admin'
    renderDashboard('/dashboard?tab=pipelineHealth')
    expect(screen.getByTestId('not-found-page')).toBeTruthy()
  })

  it('renders not-found for org-only and pipelineHealth tabs while orgLoading, but not the overview', () => {
    mockAuthValues.orgLoading = true
    const { unmount } = renderDashboard('/dashboard?tab=smbAdvisor')
    expect(screen.getByTestId('not-found-page')).toBeTruthy()
    unmount()
    renderDashboard('/dashboard')
    expect(screen.getByText('Overview')).toBeTruthy()
  })
})
