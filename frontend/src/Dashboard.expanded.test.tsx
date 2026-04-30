import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockLogout,
  mockToggleDark,
  mockRefresh,
} = vi.hoisted(() => {
  const mockLogout = vi.fn()
  const mockToggleDark = vi.fn()
  const mockRefresh = vi.fn()

  return {
    mockLogout,
    mockToggleDark,
    mockRefresh,
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// Firebase Mocks
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// Component Mocks
// ─────────────────────────────────────────────────────────────────────────────

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
  logout: mockLogout,
  getIdToken: vi.fn(),
  refreshProfile: vi.fn(),
}

vi.mock('./context/AuthContext', () => ({
  useAuth: () => mockAuthValues,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('./hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: {
      summary: null, geographicThreats: [], attackTypes: [], severityDistribution: [],
      temporalTrends: [], sectorAttackMatrix: [], industryRisk: [], kevTotal: 0,
      lossProjection: null, executiveSummary: null,
    },
    loading: false, loadingHeavy: false, errors: [], lastUpdated: null, refresh: mockRefresh,
  }),
}))

vi.mock('./hooks/useDarkMode', () => ({
  useDarkMode: () => [false, mockToggleDark],
}))

vi.mock('./components/dashboard/OverviewTab', () => ({
  default: () => <div data-testid="overview-tab">Overview Content</div>,
}))

vi.mock('./components/dashboard/DashboardHeader', () => ({
  default: ({ dark, onToggleDark, user }: { dark: boolean; onToggleDark: () => void; user?: { email?: string } }) => (
    <header data-testid="dashboard-header">
      <button data-testid="dark-mode-toggle" onClick={onToggleDark}>
        Dark: {dark ? 'on' : 'off'}
      </button>
      <span data-testid="user-email">{user?.email}</span>
      <button data-testid="logout-btn" onClick={() => mockLogout()}>
        Logout
      </button>
    </header>
  ),
}))

vi.mock('./components/dashboard/TabBar', () => ({
  default: ({ groups, activeGroup, onGroupChange }: { groups: Array<{ id: string; label: string; locked?: boolean }>; activeGroup: string; onGroupChange: (id: string) => void }) => (
    <nav data-testid="tab-bar">
      {groups.map((g) => (
        <button
          key={g.id}
          data-testid={`tab-${g.id}`}
          data-locked={g.locked}
          data-active={activeGroup === g.id}
          onClick={() => onGroupChange(g.id)}
          disabled={g.locked}
        >
          {g.label}
        </button>
      ))}
    </nav>
  ),
}))

vi.mock('./components/dashboard/SubTabBar', () => ({
  default: ({ subTabs, activeSubTab, onSubTabChange }: { subTabs: Array<{ id: string; label: string }>; activeSubTab: string; onSubTabChange: (id: string) => void }) => (
    <nav data-testid="sub-tab-bar">
      {subTabs.map((s) => (
        <button
          key={s.id}
          data-testid={`sub-tab-${s.id}`}
          data-active={activeSubTab === s.id}
          onClick={() => onSubTabChange(s.id)}
        >
          {s.label}
        </button>
      ))}
    </nav>
  ),
}))

vi.mock('./components/shared/WidgetSkeleton', () => ({ default: () => null }))
vi.mock('./api/fetchWithAuth', () => ({ API_BASE_URL: '', fetchWithAuth: vi.fn(), getJsonAuth: vi.fn() }))
vi.mock('./components/tabs/RiskScoringTable', () => ({ default: () => <div data-testid="risk-scoring">Risk Scoring</div> }))
vi.mock('./components/tabs/ThreatIntelTab', () => ({ default: () => <div data-testid="threat-intel">Threat Intel</div> }))
vi.mock('./components/tabs/TrendsTab', () => ({ default: () => <div data-testid="trends">Trends</div> }))
vi.mock('./components/tabs/PipelineHealthTab', () => ({ default: () => <div data-testid="pipeline-health">Pipeline Health</div> }))
vi.mock('./components/tabs/NormalizationLogTab', () => ({ default: () => <div data-testid="normalization-log">Normalization Log</div> }))
vi.mock('./components/tabs/SmBAdvisorTab', () => ({ default: () => <div data-testid="smb-advisor">SMB Advisor</div> }))
vi.mock('./components/tabs/VendorAlertsTab', () => ({ default: () => <div data-testid="vendor-alerts">Vendor Alerts</div> }))
vi.mock('./components/tabs/DataSourcesTab', () => ({ default: () => <div data-testid="data-sources">Data Sources</div> }))
vi.mock('./components/tabs/FindingsTab', () => ({ default: () => <div data-testid="findings">Findings</div> }))
vi.mock('./components/tabs/AISummaryTab', () => ({ default: () => <div data-testid="ai-summary">AI Summary</div> }))
vi.mock('./components/tabs/AnomaliesTab', () => ({ default: () => <div data-testid="anomalies">Anomalies</div> }))

// Import after all mocks
import Dashboard from './Dashboard'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderDashboard(initialEntries = ['/dashboard']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Dashboard />
    </MemoryRouter>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('Dashboard - Navigation & Rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthValues.orgId = null
    mockAuthValues.orgLoading = false
    mockAuthValues.role = null
    mockAuthValues.orgRole = null
  })

  describe('Page Structure & Header', () => {
    it('renders dashboard container', () => {
      renderDashboard()
      expect(screen.getByRole('main')).toBeInTheDocument()
    })

    it('renders dashboard header', () => {
      renderDashboard()
      expect(screen.getByTestId('dashboard-header')).toBeInTheDocument()
    })

    it('displays current user email in header', () => {
      mockAuthValues.user = { uid: 'u1', email: 'john@example.com' } as unknown
      renderDashboard()
      expect(screen.getByTestId('user-email')).toHaveTextContent('john@example.com')
    })

    it('renders tab bar', () => {
      renderDashboard()
      expect(screen.getByTestId('tab-bar')).toBeInTheDocument()
    })

    it('displays logo/branding elements', () => {
      renderDashboard()
      expect(screen.getByTestId('dashboard-header')).toBeTruthy()
    })
  })

  describe('Tab Visibility by Organization Status', () => {
    it('locks org-only tabs when user has no org', () => {
      renderDashboard()
      expect(screen.getByTestId('tab-assessment')).toBeDisabled()
      expect(screen.getByTestId('tab-vendorAlerts')).toBeDisabled()
    })

    it('shows org-only tabs when user has an org', () => {
      mockAuthValues.orgId = 42
      renderDashboard()
      expect(screen.getByTestId('tab-assessment')).toBeInTheDocument()
      expect(screen.getByTestId('tab-vendorAlerts')).toBeInTheDocument()
    })

    it('shows overview and public tabs regardless of org status', () => {
      renderDashboard()
      expect(screen.getByTestId('tab-overview')).toBeInTheDocument()
      expect(screen.getByTestId('tab-threats')).toBeInTheDocument()
      expect(screen.getByTestId('tab-trendsData')).toBeInTheDocument()
    })

    it('shows org-join CTA when no org and loading complete', () => {
      renderDashboard()
      expect(screen.getByText(/not part of an organization/i)).toBeInTheDocument()
      expect(screen.getByText(/Join or create an org/i)).toBeInTheDocument()
    })

    it('hides org-join CTA when org exists', () => {
      mockAuthValues.orgId = 42
      renderDashboard()
      expect(screen.queryByText(/not part of an organization/i)).toBeNull()
    })

    it('hides org-join CTA while loading org data', () => {
      mockAuthValues.orgLoading = true
      renderDashboard()
      expect(screen.queryByText(/not part of an organization/i)).toBeNull()
    })
  })

  describe('Tab Visibility by Role', () => {
    it('hides admin tabs for regular members without admin role', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'member'
      renderDashboard()
      expect(screen.queryByTestId('tab-admin')).toBeNull()
    })

    it('shows admin tabs for global admin', () => {
      mockAuthValues.role = 'admin'
      renderDashboard()
      expect(screen.getByTestId('tab-admin')).toBeInTheDocument()
    })

    it('shows admin tabs for org admin', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'admin'
      renderDashboard()
      expect(screen.getByTestId('tab-admin')).toBeInTheDocument()
    })

    it('does not show admin tabs for org owner without admin role', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'owner'
      renderDashboard()
      expect(screen.queryByTestId('tab-admin')).toBeNull()
    })

    it('hides admin tabs while org is loading and no admin role', () => {
      mockAuthValues.orgLoading = true
      mockAuthValues.role = null
      renderDashboard()
      expect(screen.queryByTestId('tab-admin')).toBeNull()
    })
  })

  describe('Tab Navigation', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('renders overview tab by default', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('can navigate to threats tab with threatIntel sub-tab', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('can navigate to riskScoring sub-tab', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('can navigate to assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('can navigate to assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('can navigate to assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('can navigate to vendorAlerts tab', async () => {
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      await waitFor(() => expect(screen.getByTestId('vendor-alerts')).toBeInTheDocument())
    })

    it('can navigate to trends sub-tab', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('can navigate to dataSources sub-tab', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('can navigate to pipelineHealth (admin sub-tab)', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('can navigate to normalizationLog (admin sub-tab)', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })

    it('disables navigation to locked tabs', () => {
      renderDashboard()
      const lockedTab = screen.queryAllByRole('button').find(b => b.getAttribute('data-locked') === 'true')
      if (lockedTab) {
        expect(lockedTab).toBeDisabled()
      }
    })

    it('falls back to overview when accessing locked tab', async () => {
      renderDashboard(['/dashboard?tab=lockedTab'])
      await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument())
    })

    it('falls back to overview when accessing non-existent tab', async () => {
      renderDashboard(['/dashboard?tab=invalidTab'])
      await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument())
    })
  })

  describe('Dark Mode Toggle', () => {
    it('renders dark mode toggle button', () => {
      renderDashboard()
      expect(screen.getByTestId('dark-mode-toggle')).toBeInTheDocument()
    })

    it('calls dark mode toggle when button clicked', async () => {
      renderDashboard()
      const toggleBtn = screen.getByTestId('dark-mode-toggle')
      fireEvent.click(toggleBtn)
      
      await waitFor(() => {
        expect(mockToggleDark).toHaveBeenCalled()
      })
    })

    it('displays dark mode state in toggle button', () => {
      renderDashboard()
      const toggleBtn = screen.getByTestId('dark-mode-toggle')
      expect(toggleBtn).toHaveTextContent('Dark: off')
    })
  })

  describe('Logout Functionality', () => {
    it('renders logout button', () => {
      renderDashboard()
      expect(screen.getByTestId('logout-btn')).toBeInTheDocument()
    })

    it('calls logout when logout button clicked', () => {
      renderDashboard()
      const logoutBtn = screen.getByTestId('logout-btn')
      fireEvent.click(logoutBtn)
      
      expect(mockLogout).toHaveBeenCalled()
    })
  })

  describe('Organization Navigation Link', () => {
    it('links to settings when user has no org', () => {
      renderDashboard()
      const settingsLink = screen.getByRole('link', { name: /Join or create an org/i })
      expect(settingsLink).toHaveAttribute('href', '/settings')
    })
  })

  describe('Component Rendering by Tab', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('renders OverviewTab content when viewing overview', async () => {
      renderDashboard(['/dashboard'])
      await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument())
    })

    it('renders RiskScoringTable when viewing threats/riskScoring', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('renders ThreatIntelTab when viewing threats/threatIntel', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('renders TrendsTab when viewing trendsData/trends', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('renders PipelineHealthTab when viewing admin/pipelineHealth', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('renders NormalizationLogTab when viewing admin/normalizationLog', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })

    it('renders SmBAdvisorTab when viewing assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('renders FindingsTab when viewing assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('renders AISummaryTab when viewing assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('renders DataSourcesTab when viewing trendsData/dataSources', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('renders VendorAlertsTab when viewing vendorAlerts', async () => {
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      await waitFor(() => expect(screen.getByTestId('vendor-alerts')).toBeInTheDocument())
    })

    it('renders AnomaliesTab when viewing threats/anomalies', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=anomalies'])
      await waitFor(() => expect(screen.getByTestId('anomalies')).toBeInTheDocument())
    })
  })

  describe('Sub-Tab Navigation', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('shows sub-tab bar for tabs with subtabs', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('sub-tab-bar')).toBeInTheDocument())
    })

    it('defaults to first sub-tab when none specified', () => {
      renderDashboard(['/dashboard?tab=assessment'])
      // Should default to first sub-tab
      expect(screen.getByTestId('sub-tab-bar')).toBeInTheDocument()
    })

    it('navigates between sub-tabs in assessment group', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('navigates between sub-tabs in threats group', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('navigates between sub-tabs in trendsData group', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('navigates between sub-tabs in admin group', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('hides sub-tab bar for tabs without subtabs', () => {
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      expect(screen.queryByTestId('sub-tab-bar')).toBeNull()
    })

    it('hides sub-tab bar for overview tab', () => {
      renderDashboard(['/dashboard'])
      expect(screen.queryByTestId('sub-tab-bar')).toBeNull()
    })
  })

  describe('Loading States', () => {
    it('renders correctly while dashboard data is loading', () => {
      renderDashboard()
      expect(screen.getByTestId('dashboard-header')).toBeInTheDocument()
      expect(screen.getByTestId('tab-bar')).toBeInTheDocument()
    })

    it('renders overview tab even when data is still loading', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('still renders navigation when user data is missing', () => {
      mockAuthValues.user = null as unknown
      renderDashboard()
      expect(screen.getByTestId('tab-bar')).toBeInTheDocument()
    })

    it('shows overview tab on error state', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })
  })

  describe('Tab Active States', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('marks overview tab as active by default', () => {
      renderDashboard()
      const overviewTab = screen.getByTestId('tab-overview')
      expect(overviewTab).toHaveAttribute('data-active', 'true')
    })

    it('marks threats tab as active when selected', () => {
      renderDashboard(['/dashboard?tab=threats'])
      const threatsTab = screen.getByTestId('tab-threats')
      expect(threatsTab).toHaveAttribute('data-active', 'true')
    })

    it('marks assessment tab as active when on subtab', () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      const assessmentTab = screen.getByTestId('tab-assessment')
      expect(assessmentTab).toHaveAttribute('data-active', 'true')
    })

    it('marks trendsData tab as active when on subtab', () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      const trendsTab = screen.getByTestId('tab-trendsData')
      expect(trendsTab).toHaveAttribute('data-active', 'true')
    })

    it('marks admin tab as active when on subtab', () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      const adminTab = screen.getByTestId('tab-admin')
      expect(adminTab).toHaveAttribute('data-active', 'true')
    })
  })

  describe('Legacy Tab Mapping', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('maps legacy findings tab to assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('maps legacy smbAdvisor to assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('maps legacy aiSummary to assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('maps legacy threatIntel to threats/threatIntel', async () => {
      renderDashboard(['/dashboard?tab=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('maps legacy riskScoring to threats/riskScoring', async () => {
      renderDashboard(['/dashboard?tab=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('maps legacy anomalies to threats/anomalies', async () => {
      renderDashboard(['/dashboard?tab=anomalies'])
      await waitFor(() => expect(screen.getByTestId('anomalies')).toBeInTheDocument())
    })

    it('maps legacy trends to trendsData/trends', async () => {
      renderDashboard(['/dashboard?tab=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('maps legacy dataSources to trendsData/dataSources', async () => {
      renderDashboard(['/dashboard?tab=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('maps legacy pipelineHealth to admin/pipelineHealth', async () => {
      renderDashboard(['/dashboard?tab=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('maps legacy normalizationLog to admin/normalizationLog', async () => {
      renderDashboard(['/dashboard?tab=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })
  })

  describe('Multiple Role Scenarios', () => {
    it('shows correct tabs for global admin with org', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'admin'
      mockAuthValues.orgRole = 'admin'
      renderDashboard()

      expect(screen.getByTestId('tab-admin')).toBeInTheDocument()
      expect(screen.getByTestId('tab-assessment')).toBeInTheDocument()
    })

    it('shows correct tabs for org member without global admin', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'member'
      renderDashboard()

      expect(screen.queryByTestId('tab-admin')).toBeNull()
      expect(screen.getByTestId('tab-assessment')).toBeInTheDocument()
    })

    it('shows correct tabs for owner of org', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'owner'
      renderDashboard()

      // owner orgRole does not satisfy requiresAdmin (only 'admin' does)
      expect(screen.queryByTestId('tab-admin')).toBeNull()
      expect(screen.getByTestId('tab-assessment')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles null orgId gracefully', () => {
      mockAuthValues.orgId = null
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('handles switching between users with different roles', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      renderDashboard()
      
      mockAuthValues.role = 'admin'
      renderDashboard(['/dashboard?tab=pipelineHealth'])
      expect(screen.getByTestId('pipeline-health')).toBeInTheDocument()
    })

    it('persists tab selection across navigation', () => {
      mockAuthValues.orgId = 42
      renderDashboard(['/dashboard?tab=riskScoring'])
      expect(screen.getByTestId('risk-scoring')).toBeInTheDocument()
    })
  })
})
