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
vi.mock('./components/dashboard/TabBar', () => ({
  default: ({ groups }: { groups: { id: string; label: string; locked?: boolean; subTabs?: { id: string; label: string }[] }[] }) => (
    <nav>
      {groups.filter(g => !g.locked).flatMap(g => [
        <span key={g.id} data-testid={`tab-${g.id}`}>{g.label}</span>,
        ...(g.subTabs ?? []).map(s => <span key={s.id} data-testid={`tab-${s.id}`}>{s.label}</span>),
      ])}
    </nav>
  ),
}))
vi.mock('./api/fetchWithAuth', () => ({ API_BASE_URL: '', fetchWithAuth: vi.fn(), getJsonAuth: vi.fn() }))
vi.mock('./components/shared/WidgetSkeleton', () => ({ default: () => null }))

import Dashboard from './Dashboard'

function renderDashboard() {
  return render(
    <MemoryRouter>
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

  it('hides org-only tabs when user has no org', () => {
    renderDashboard()
    expect(screen.queryByTestId('tab-smbAdvisor')).toBeNull()
    expect(screen.queryByTestId('tab-findings')).toBeNull()
    expect(screen.queryByTestId('tab-aiSummary')).toBeNull()
    expect(screen.queryByTestId('tab-vendorAlerts')).toBeNull()
  })

  it('shows org-only tabs when user has an org', () => {
    mockAuthValues.orgId = 42
    renderDashboard()
    expect(screen.getByTestId('tab-smbAdvisor')).toBeTruthy()
    expect(screen.getByTestId('tab-findings')).toBeTruthy()
    expect(screen.getByTestId('tab-aiSummary')).toBeTruthy()
    expect(screen.getByTestId('tab-vendorAlerts')).toBeTruthy()
  })

  it('hides pipelineHealth for a regular org member', () => {
    mockAuthValues.orgId = 42
    mockAuthValues.role = 'viewer'
    mockAuthValues.orgRole = 'member'
    renderDashboard()
    expect(screen.queryByTestId('tab-pipelineHealth')).toBeNull()
  })

  it('shows pipelineHealth for a global admin', () => {
    mockAuthValues.role = 'admin'
    mockAuthValues.orgRole = null
    renderDashboard()
    expect(screen.getByTestId('tab-pipelineHealth')).toBeTruthy()
  })

  it('shows pipelineHealth for an org admin', () => {
    mockAuthValues.orgId = 42
    mockAuthValues.role = 'viewer'
    mockAuthValues.orgRole = 'admin'
    renderDashboard()
    expect(screen.getByTestId('tab-pipelineHealth')).toBeTruthy()
  })

  it('hides all org-only and pipelineHealth tabs while orgLoading', () => {
    mockAuthValues.orgLoading = true
    renderDashboard()
    expect(screen.queryByTestId('tab-smbAdvisor')).toBeNull()
    expect(screen.queryByTestId('tab-pipelineHealth')).toBeNull()
    // Non-org tabs should still be visible
    expect(screen.getByTestId('tab-overview')).toBeTruthy()
  })

  it('shows org-join CTA when user has no org and loading is done', () => {
    renderDashboard()
    expect(screen.getByText(/not part of an organization/i)).toBeTruthy()
  })
})
